"""CELL 추출기"""
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET
import subprocess

class CellExtractor:
    """CELL 텍스트 추출기 - hwp5txt 우선 사용"""
    
    def extract_text(self, file_path: str) -> str:
        """CELL 파일에서 텍스트 추출 (hwp5txt 우선)"""
        # 1순위: hwp5txt 사용 (한컴 문서 형식 지원)
        text = self._extract_with_hwp5txt(file_path)
        if text:
            return text
        
        # 2순위: ZIP/XML 기반 추출
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
            # 3순위: pyhwpx fallback
            try:
                from pyhwpx import HwpFile
                hwp = HwpFile(file_path)
                text = hwp.get_text()
                hwp.close()
                return text.strip()
            except:
                return ""
    
    def _extract_with_hwp5txt(self, file_path: str) -> str:
        """hwp5txt 명령어로 텍스트 추출"""
        try:
            # hwp5txt --text로 텍스트만 추출
            result = subprocess.run(
                ['hwp5txt', '--text', file_path],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=30
            )
            
            if result.returncode == 0:
                text = result.stdout.strip()
                if len(text) > 10:
                    return text
            
            # --text 옵션 실패시 일반 출력 시도
            result = subprocess.run(
                ['hwp5txt', file_path],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=30
            )
            
            if result.returncode == 0:
                text = result.stdout.strip()
                if len(text) > 10:
                    return text
                    
        except subprocess.TimeoutExpired:
            return ""
        except FileNotFoundError:
            # hwp5txt가 설치되지 않음
            return ""
        except Exception:
            pass
        
        return ""
