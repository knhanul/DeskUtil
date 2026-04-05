"""CELL 추출기"""
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

class CellExtractor:
    """CELL 텍스트 추출기"""
    
    def extract_text(self, file_path: str) -> str:
        """CELL 파일에서 텍스트 추출 (ZIP/XML 기반)"""
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_file:
                text = ""
                
                # worksheets 폴더의 XML 파일들에서 텍스트 추출
                for file_info in zip_file.filelist:
                    if 'worksheets/' in file_info.filename and file_info.filename.endswith('.xml'):
                        try:
                            with zip_file.open(file_info.filename) as xml_file:
                                tree = ET.parse(xml_file)
                                root = tree.getroot()
                                
                                # 셀 텍스트 추출
                                for elem in root.iter():
                                    if elem.tag.endswith('v') and elem.text:  # 셀 값
                                        text += elem.text + " "
                                    elif elem.tag.endswith('t') and elem.text:  # 인라인 텍스트
                                        text += elem.text + " "
                        except:
                            continue
                
                return text.strip()
        except:
            # pyhwpx fallback
            try:
                from pyhwpx import HwpFile
                hwp = HwpFile(file_path)
                text = hwp.get_text()
                hwp.close()
                return text.strip()
            except:
                return ""
