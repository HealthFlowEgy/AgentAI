"""
OCR Service for document processing
Supports: Images (JPG, PNG), PDFs, ID cards, bills, EOBs
Uses Tesseract OCR with image preprocessing for optimal results
"""

import pytesseract
from PIL import Image
import cv2
import numpy as np
from pdf2image import convert_from_path
import logging
from typing import Dict, Any, List, Optional
import re
from pathlib import Path
import tempfile

logger = logging.getLogger(__name__)


class OCRService:
    """OCR processing service with advanced preprocessing"""
    
    def __init__(self):
        # Configure Tesseract path (adjust for your system)
        # pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'
        
        # Supported languages (English and Arabic for Egyptian documents)
        self.languages = 'eng+ara'
    
    async def process_file(
        self,
        file_path: str,
        document_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process file with OCR
        
        Args:
            file_path: Path to file
            document_type: Optional hint (id_card, bill, eob, medical_record)
        
        Returns:
            Dict with extracted text and structured data
        """
        logger.info(f"📄 Processing file with OCR: {file_path}")
        
        try:
            file_path_obj = Path(file_path)
            file_extension = file_path_obj.suffix.lower()
            
            # Determine file type and process
            if file_extension == '.pdf':
                result = await self._process_pdf(file_path)
            elif file_extension in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']:
                result = await self._process_image(file_path)
            else:
                raise ValueError(f"Unsupported file type: {file_extension}")
            
            # Extract structured data based on document type
            if document_type:
                structured_data = await self._extract_structured_data(
                    result['text'],
                    document_type
                )
                result['structured_data'] = structured_data
            else:
                # Auto-detect document type and extract
                detected_type = self._detect_document_type(result['text'])
                structured_data = await self._extract_structured_data(
                    result['text'],
                    detected_type
                )
                result['structured_data'] = structured_data
                result['detected_type'] = detected_type
            
            logger.info(
                f"✅ OCR completed: {len(result['text'])} characters extracted, "
                f"confidence: {result.get('confidence', 0):.1f}%"
            )
            
            return result
        
        except Exception as e:
            logger.error(f"❌ OCR processing failed: {e}", exc_info=True)
            raise
    
    async def _process_image(self, image_path: str) -> Dict[str, Any]:
        """Process image with OCR"""
        # Load image
        image = cv2.imread(image_path)
        
        if image is None:
            raise ValueError(f"Failed to load image: {image_path}")
        
        # Preprocess image for better OCR results
        processed_image = self._preprocess_image(image)
        
        # Perform OCR
        text = pytesseract.image_to_string(
            processed_image,
            lang=self.languages,
            config='--psm 6 --oem 3'  # Page segmentation mode 6, LSTM OCR engine
        )
        
        # Get detailed OCR data with confidence scores
        data = pytesseract.image_to_data(
            processed_image,
            lang=self.languages,
            output_type=pytesseract.Output.DICT
        )
        
        # Calculate average confidence
        confidences = [conf for conf in data['conf'] if conf > 0]
        avg_confidence = np.mean(confidences) if confidences else 0
        
        # Extract words with high confidence
        high_confidence_words = [
            data['text'][i]
            for i in range(len(data['text']))
            if data['conf'][i] > 60 and data['text'][i].strip()
        ]
        
        return {
            'text': text.strip(),
            'confidence': avg_confidence,
            'word_count': len(high_confidence_words),
            'filename': Path(image_path).name,
            'type': 'image',
            'language': self.languages,
            'words': high_confidence_words
        }
    
    async def _process_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """Process PDF with OCR"""
        # Convert PDF to images
        images = convert_from_path(pdf_path, dpi=300)
        
        all_text = []
        total_confidence = 0
        all_words = []
        
        for page_num, image in enumerate(images, 1):
            logger.info(f"Processing page {page_num}/{len(images)}...")
            
            # Convert PIL to OpenCV format
            opencv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            
            # Preprocess
            processed = self._preprocess_image(opencv_image)
            
            # OCR
            text = pytesseract.image_to_string(
                processed,
                lang=self.languages,
                config='--psm 6 --oem 3'
            )
            all_text.append(f"--- Page {page_num} ---\n{text}")
            
            # Get confidence
            data = pytesseract.image_to_data(
                processed,
                output_type=pytesseract.Output.DICT
            )
            confidences = [conf for conf in data['conf'] if conf > 0]
            if confidences:
                page_conf = np.mean(confidences)
                total_confidence += page_conf
            
            # Extract words
            page_words = [
                data['text'][i]
                for i in range(len(data['text']))
                if data['conf'][i] > 60 and data['text'][i].strip()
            ]
            all_words.extend(page_words)
        
        combined_text = '\n\n'.join(all_text)
        avg_confidence = total_confidence / len(images) if images else 0
        
        return {
            'text': combined_text.strip(),
            'confidence': avg_confidence,
            'pages': len(images),
            'word_count': len(all_words),
            'filename': Path(pdf_path).name,
            'type': 'pdf',
            'language': self.languages,
            'words': all_words
        }
    
    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for better OCR results
        
        Steps:
        1. Convert to grayscale
        2. Denoise
        3. Increase contrast
        4. Binarization (thresholding)
        5. Deskew (optional)
        """
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(gray, h=10)
        
        # Increase contrast using CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        contrast = clahe.apply(denoised)
        
        # Adaptive thresholding for better binarization
        binary = cv2.adaptiveThreshold(
            contrast,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11,
            2
        )
        
        # Morphological operations to remove noise
        kernel = np.ones((1, 1), np.uint8)
        morph = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        
        return morph
    
    def _detect_document_type(self, text: str) -> str:
        """
        Detect document type from text content
        
        Returns: id_card, bill, eob, medical_record, or unknown
        """
        text_lower = text.lower()
        
        # ID Card indicators
        id_indicators = ['national id', 'رقم قومي', 'passport', 'جواز سفر', 'date of birth', 'تاريخ الميلاد']
        if any(indicator in text_lower for indicator in id_indicators):
            return 'id_card'
        
        # Bill indicators
        bill_indicators = ['invoice', 'bill', 'فاتورة', 'total amount', 'المبلغ الإجمالي', 'payment due']
        if any(indicator in text_lower for indicator in bill_indicators):
            return 'bill'
        
        # EOB indicators
        eob_indicators = ['explanation of benefits', 'eob', 'claim number', 'رقم المطالبة', 'allowed amount', 'patient responsibility']
        if any(indicator in text_lower for indicator in eob_indicators):
            return 'eob'
        
        # Medical record indicators
        medical_indicators = ['diagnosis', 'التشخيص', 'prescription', 'وصفة طبية', 'icd', 'cpt', 'physician']
        if any(indicator in text_lower for indicator in medical_indicators):
            return 'medical_record'
        
        return 'unknown'
    
    async def _extract_structured_data(
        self,
        text: str,
        document_type: str
    ) -> Dict[str, Any]:
        """Extract structured data based on document type"""
        
        if document_type == 'id_card':
            return self._extract_id_card_data(text)
        elif document_type == 'bill':
            return self._extract_bill_data(text)
        elif document_type == 'eob':
            return self._extract_eob_data(text)
        elif document_type == 'medical_record':
            return self._extract_medical_record_data(text)
        else:
            return self._extract_general_data(text)
    
    def _extract_id_card_data(self, text: str) -> Dict[str, Any]:
        """Extract data from ID card"""
        data = {}
        
        # Extract Egyptian National ID (14 digits)
        national_id_pattern = r'\b\d{14}\b'
        national_id_match = re.search(national_id_pattern, text)
        if national_id_match:
            data['national_id'] = national_id_match.group(0)
        
        # Extract name (Arabic or English - simplified)
        # Look for capitalized words that might be names
        name_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b'
        name_matches = re.findall(name_pattern, text)
        if name_matches:
            data['name'] = name_matches[0]
        
        # Extract date of birth (multiple formats)
        dob_patterns = [
            r'\b\d{4}-\d{2}-\d{2}\b',  # YYYY-MM-DD
            r'\b\d{2}/\d{2}/\d{4}\b',  # DD/MM/YYYY
            r'\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b'  # DD Month YYYY
        ]
        for pattern in dob_patterns:
            dob_match = re.search(pattern, text, re.IGNORECASE)
            if dob_match:
                data['date_of_birth'] = dob_match.group(0)
                break
        
        # Extract gender
        if re.search(r'\b(male|ذكر)\b', text, re.IGNORECASE):
            data['gender'] = 'male'
        elif re.search(r'\b(female|أنثى)\b', text, re.IGNORECASE):
            data['gender'] = 'female'
        
        # Extract address (simplified - look for governorate names)
        governorates = ['cairo', 'giza', 'alexandria', 'aswan', 'asyut', 'beheira', 
                       'القاهرة', 'الجيزة', 'الإسكندرية']
        for gov in governorates:
            if gov in text.lower():
                data['governorate'] = gov
                break
        
        return data
    
    def _extract_bill_data(self, text: str) -> Dict[str, Any]:
        """Extract data from medical bill"""
        data = {}
        
        # Extract invoice/bill number
        invoice_patterns = [
            r'invoice\s*#?\s*:?\s*(\d+)',
            r'bill\s*#?\s*:?\s*(\d+)',
            r'فاتورة\s*رقم\s*:?\s*(\d+)'
        ]
        for pattern in invoice_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data['invoice_number'] = match.group(1)
                break
        
        # Extract date
        date_pattern = r'\b\d{4}-\d{2}-\d{2}\b|\b\d{2}/\d{2}/\d{4}\b'
        date_match = re.search(date_pattern, text)
        if date_match:
            data['date'] = date_match.group(0)
        
        # Extract amounts
        amount_patterns = [
            r'total\s*:?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'amount\s*:?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'المبلغ\s*:?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)'
        ]
        for pattern in amount_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data['total_amount'] = match.group(1).replace(',', '')
                break
        
        # Extract patient name
        patient_pattern = r'patient\s*:?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})'
        patient_match = re.search(patient_pattern, text, re.IGNORECASE)
        if patient_match:
            data['patient_name'] = patient_match.group(1)
        
        # Extract CPT codes
        cpt_pattern = r'\b\d{5}\b'
        cpt_codes = re.findall(cpt_pattern, text)
        if cpt_codes:
            data['cpt_codes'] = cpt_codes
        
        # Extract ICD codes
        icd_pattern = r'\b[A-Z]\d{2}(?:\.\d{1,2})?\b'
        icd_codes = re.findall(icd_pattern, text)
        if icd_codes:
            data['icd_codes'] = icd_codes
        
        return data
    
    def _extract_eob_data(self, text: str) -> Dict[str, Any]:
        """Extract data from Explanation of Benefits"""
        data = {}
        
        # Extract claim number
        claim_pattern = r'claim\s*#?\s*:?\s*([A-Z0-9-]+)'
        claim_match = re.search(claim_pattern, text, re.IGNORECASE)
        if claim_match:
            data['claim_number'] = claim_match.group(1)
        
        # Extract patient name
        patient_pattern = r'patient\s*:?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})'
        patient_match = re.search(patient_pattern, text, re.IGNORECASE)
        if patient_match:
            data['patient_name'] = patient_match.group(1)
        
        # Extract billed amount
        billed_pattern = r'billed\s*:?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)'
        billed_match = re.search(billed_pattern, text, re.IGNORECASE)
        if billed_match:
            data['billed_amount'] = billed_match.group(1).replace(',', '')
        
        # Extract allowed amount
        allowed_pattern = r'allowed\s*:?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)'
        allowed_match = re.search(allowed_pattern, text, re.IGNORECASE)
        if allowed_match:
            data['allowed_amount'] = allowed_match.group(1).replace(',', '')
        
        # Extract patient responsibility
        patient_resp_pattern = r'patient\s+responsibility\s*:?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)'
        patient_resp_match = re.search(patient_resp_pattern, text, re.IGNORECASE)
        if patient_resp_match:
            data['patient_responsibility'] = patient_resp_match.group(1).replace(',', '')
        
        # Extract denial codes
        denial_pattern = r'\b(CO|PR)-?\d{1,3}\b'
        denial_codes = re.findall(denial_pattern, text)
        if denial_codes:
            data['denial_codes'] = denial_codes
        
        return data
    
    def _extract_medical_record_data(self, text: str) -> Dict[str, Any]:
        """Extract data from medical record"""
        data = {}
        
        # Extract ICD codes
        icd_pattern = r'\b[A-Z]\d{2}(?:\.\d{1,2})?\b'
        icd_codes = re.findall(icd_pattern, text)
        if icd_codes:
            data['icd_codes'] = list(set(icd_codes))  # Remove duplicates
        
        # Extract CPT codes
        cpt_pattern = r'\b\d{5}\b'
        cpt_codes = re.findall(cpt_pattern, text)
        if cpt_codes:
            data['cpt_codes'] = list(set(cpt_codes))
        
        # Extract dates
        date_pattern = r'\b\d{4}-\d{2}-\d{2}\b|\b\d{2}/\d{2}/\d{4}\b'
        dates = re.findall(date_pattern, text)
        if dates:
            data['dates'] = dates
        
        # Extract medications (simplified - look for common drug name patterns)
        # This is very basic - would need a drug database for accurate extraction
        medication_pattern = r'\b([A-Z][a-z]+(?:in|ol|ide|ate|one))\s+\d+\s*(?:mg|mcg|ml)\b'
        medications = re.findall(medication_pattern, text)
        if medications:
            data['medications'] = list(set(medications))
        
        return data
    
    def _extract_general_data(self, text: str) -> Dict[str, Any]:
        """Extract general data from unknown document type"""
        data = {}
        
        # Extract all dates
        date_pattern = r'\b\d{4}-\d{2}-\d{2}\b|\b\d{2}/\d{2}/\d{4}\b'
        dates = re.findall(date_pattern, text)
        if dates:
            data['dates'] = dates
        
        # Extract all amounts
        amount_pattern = r'\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:EGP|USD|LE|pounds?|dollars?)?'
        amounts = re.findall(amount_pattern, text, re.IGNORECASE)
        if amounts:
            data['amounts'] = amounts
        
        # Extract phone numbers
        phone_pattern = r'\b(?:\+20|0)?1[0-2,5]\d{8}\b'
        phones = re.findall(phone_pattern, text)
        if phones:
            data['phone_numbers'] = phones
        
        # Extract emails
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        if emails:
            data['emails'] = emails
        
        # Extract any codes (ICD, CPT, etc.)
        icd_pattern = r'\b[A-Z]\d{2}(?:\.\d{1,2})?\b'
        icd_codes = re.findall(icd_pattern, text)
        if icd_codes:
            data['possible_icd_codes'] = list(set(icd_codes))
        
        cpt_pattern = r'\b\d{5}\b'
        cpt_codes = re.findall(cpt_pattern, text)
        if cpt_codes:
            data['possible_cpt_codes'] = list(set(cpt_codes))
        
        return data
    
    async def extract_table_data(self, image_path: str) -> List[List[str]]:
        """
        Extract table data from image
        
        Uses OpenCV to detect table structure
        """
        image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        
        # Threshold the image
        _, binary = cv2.threshold(image, 128, 255, cv2.THRESH_BINARY_INV)
        
        # Detect horizontal and vertical lines
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
        
        horizontal_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel)
        vertical_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel)
        
        # Combine lines to get table structure
        table_structure = cv2.add(horizontal_lines, vertical_lines)
        
        # Find contours (table cells)
        contours, _ = cv2.findContours(
            table_structure,
            cv2.RETR_TREE,
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        # Extract text from each cell
        cells = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w > 20 and h > 20:  # Filter small contours
                cell_image = image[y:y+h, x:x+w]
                cell_text = pytesseract.image_to_string(cell_image, lang=self.languages)
                cells.append({
                    'x': x,
                    'y': y,
                    'text': cell_text.strip()
                })
        
        # Sort cells into rows and columns
        cells.sort(key=lambda c: (c['y'], c['x']))
        
        # Group into rows (simplified)
        rows = []
        current_row = []
        last_y = -1
        
        for cell in cells:
            if last_y == -1 or abs(cell['y'] - last_y) < 10:
                current_row.append(cell['text'])
            else:
                if current_row:
                    rows.append(current_row)
                current_row = [cell['text']]
            last_y = cell['y']
        
        if current_row:
            rows.append(current_row)
        
        return rows
