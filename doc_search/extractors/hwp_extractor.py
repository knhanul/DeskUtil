"""HWP 추출기"""
from pathlib import Path
import olefile
import zipfile
import xml.etree.ElementTree as ET
import subprocess
import tempfile
import os

class HWPExtractor:
    """HWP/HWPX 텍스트 추출기 - hwp5txt 우선 사용"""
    
    def extract_text(self, file_path: str) -> str:
        """HWP/HWPX에서 텍스트 추출"""
        path = Path(file_path)
        
        if path.suffix.lower() == '.hwpx':
            return self._extract_hwpx(file_path)
        else:
            return self._extract_hwp(file_path)
    
    def _extract_hwp(self, file_path: str) -> str:
        """HWP 파일에서 텍스트 추출 (hwp5txt 우선, pyhwpx fallback)"""
        path = Path(file_path)
        
        # 1순위: hwp5txt 사용
        text = self._extract_with_hwp5txt(file_path)
        if text:
            return text
        
        # 2순위: pyhwpx 사용
        try:
            from pyhwpx import HwpFile
            hwp = HwpFile(file_path)
            text = hwp.get_text()
            hwp.close()
            return text.strip()
        except:
            pass
        
        # 3순위: olefile 기반 기본 추출
        try:
            if not olefile.isOleFile(file_path):
                return ""
            
            ole = olefile.OleFileIO(file_path)
            
            # FileHeader 확인
            if not ole.exists('FileHeader'):
                ole.close()
                return ""
            
            ole.close()
            return ""
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
                timeout=30  # 30초 타임아웃
            )
            
            if result.returncode == 0:
                text = result.stdout.strip()
                # 빈 결과나 너무 짧은 결과는 무시
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
    
    def _extract_hwpx(self, file_path: str) -> str:
        """HWPX 파일에서 텍스트 추출 (hwp5txt 우선, ZIP/XML fallback)"""
        # 1순위: hwp5txt 시도 (최신 버전은 hwpx도 지원)
        text = self._extract_with_hwp5txt(file_path)
        if text:
            return text
        
        # 2순위: ZIP/XML 기반 추출
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_file:
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
