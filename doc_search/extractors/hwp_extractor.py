"""HWP 추출기"""
from pathlib import Path
import olefile
import zipfile
import xml.etree.ElementTree as ET

class HWPExtractor:
    """HWP/HWPX 텍스트 추출기"""
    
    def extract_text(self, file_path: str) -> str:
        """HWP/HWPX에서 텍스트 추출"""
        path = Path(file_path)
        
        if path.suffix.lower() == '.hwpx':
            return self._extract_hwpx(file_path)
        else:
            return self._extract_hwp(file_path)
    
    def _extract_hwp(self, file_path: str) -> str:
        """HWP 파일에서 텍스트 추출 (olefile 기반)"""
        try:
            if not olefile.isOleFile(file_path):
                return ""
            
            ole = olefile.OleFileIO(file_path)
            
            # FileHeader 확인
            if not ole.exists('FileHeader'):
                ole.close()
                return ""
            
            ole.close()
            
            # pyhwpx 시도
            try:
                from pyhwpx import HwpFile
                hwp = HwpFile(file_path)
                text = hwp.get_text()
                hwp.close()
                return text.strip()
            except:
                pass
            
            return ""
        except:
            return ""
    
    def _extract_hwpx(self, file_path: str) -> str:
        """HWPX 파일에서 텍스트 추출 (ZIP/XML 기반)"""
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_file:
                # Contents 폴더의 XML 파일들에서 텍스트 추출
                text = ""
                for file_info in zip_file.filelist:
                    if file_info.filename.startswith('Contents/') and file_info.filename.endswith('.xml'):
                        try:
                            with zip_file.open(file_info.filename) as xml_file:
                                tree = ET.parse(xml_file)
                                root = tree.getroot()
                                
                                # 모든 텍스트 노드 추출
                                for elem in root.iter():
                                    if elem.text:
                                        text += elem.text + " "
                        except:
                            continue
                
                return text.strip()
        except:
            return ""
