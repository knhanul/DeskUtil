"""통합 문서 미리보기 - QTextBrowser 기반 (WebEngine 없이 동작)"""
import base64
import html
import zipfile
from pathlib import Path
from typing import Optional

# PySide6 / PyQt6 호환 임포트
try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QTextBrowser, QWidget
except ImportError:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QTextBrowser, QWidget

from doc_search.extractors import get_extractor


class IntegratedPreviewer(QTextBrowser):
    """통합 문서 미리보기 - QTextBrowser 기반 (WebEngine 없이 동작)"""
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setOpenExternalLinks(False)
        self._show_loading_state()
    
    def preview_file(self, file_path: str, file_name: str) -> None:
        """파일 미리보기 (텍스트 추출 방식)"""
        if not file_path or not Path(file_path).exists():
            self._show_error("파일을 찾을 수 없습니다.")
            return
        
        self.setHtml("<div style='text-align:center; padding:40px;'>미리보기 로딩 중...</div>")
        
        try:
            suffix = Path(file_path).suffix.lower()
            
            # HWPX는 이미지 추출 시도
            if suffix == '.hwpx':
                image_html = self._try_hwpx_image(file_path)
                if image_html:
                    self.setHtml(image_html)
                    return
            
            # PDF는 텍스트 추출 시도
            if suffix == '.pdf':
                try:
                    import fitz
                    doc = fitz.open(file_path)
                    text = ""
                    for page in doc[:3]:  # 처음 3페이지만
                        text += page.get_text()
                    doc.close()
                    if text.strip():
                        html_content = self._wrap_in_paper_card_html(text, file_name, "PDF")
                        self.setHtml(html_content)
                        return
                except:
                    pass
            
            # 일반 텍스트 추출
            extractor = get_extractor(file_path)
            if extractor:
                text = extractor.extract_text(file_path) or ""
                if text.strip():
                    html_content = self._wrap_in_paper_card_html(text, file_name, suffix.upper()[1:])
                    self.setHtml(html_content)
                    return
            
            self._show_error("미리보기를 생성할 수 없습니다.")
            
        except Exception as e:
            self._show_error(f"미리보기 오류: {str(e)}")
    
    def _try_hwpx_image(self, file_path: str) -> str:
        """HWPX 파일에서 미리보기 이미지 추출 시도"""
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                preview_path = 'Preview/PrvImage.png'
                if preview_path not in zf.namelist():
                    return ""
                
                with zf.open(preview_path) as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')
                
                return f"""<!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <style>
                        body {{
                            margin: 0;
                            background: #1a1a1a;
                            display: flex;
                            justify-content: center;
                            align-items: center;
                            min-height: 100vh;
                        }}
                        .container {{
                            text-align: center;
                        }}
                        .label {{
                            color: #888;
                            font-family: 'Segoe UI', sans-serif;
                            font-size: 12px;
                            margin-bottom: 20px;
                        }}
                        img {{
                            max-width: 90%;
                            max-height: 80vh;
                            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
                        }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="label">📄 HWPX 미리보기 이미지</div>
                        <img src="data:image/png;base64,{image_data}" alt="Preview">
                    </div>
                </body>
                </html>"""
        except:
            return ""
    
    def _wrap_in_paper_card_html(self, text: str, file_name: str, file_type: str) -> str:
        """추출된 텍스트를 Paper Card 스타일 HTML로 변환"""
        lines = text.split('\n', 1)
        title = lines[0].strip() if lines else "제목 없음"
        body = lines[1].strip() if len(lines) > 1 else ""
        
        # 추가 줄 제한
        body_lines = body.split('\n')[:300]
        body = '\n'.join(body_lines)
        
        # HTML 이스케이프
        title_escaped = html.escape(title)
        body_escaped = html.escape(body).replace('\n', '<br>')
        file_name_escaped = html.escape(file_name)
        
        # 확장자별 아이콘
        icon_map = {
            'HWP': '📄',
            'HWPX': '📄',
            'DOCX': '📝',
            'CELL': '📊',
            'XLSX': '📊',
            'PDF': '📕',
            'TXT': '📃',
        }
        file_icon = icon_map.get(file_type, '📄')
        
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: 'Malgun Gothic', 'Segoe UI', 'Apple SD Gothic Neo', -apple-system, sans-serif;
            background: linear-gradient(135deg, #e9ecef 0%, #dee2e6 100%);
            margin: 0;
            padding: 30px 20px;
        }}
        .document-container {{
            max-width: 800px;
            margin: 0 auto;
        }}
        .metadata-bar {{
            background: rgba(255, 255, 255, 0.95);
            border-radius: 12px;
            padding: 12px 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
            font-size: 13px;
            color: #495057;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .file-icon {{
            font-size: 18px;
        }}
        .file-name {{
            font-weight: 600;
            color: #212529;
        }}
        .file-type {{
            margin-left: auto;
            background: #e7f5ff;
            color: #1864ab;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 600;
        }}
        .paper-card {{
            background: #ffffff;
            border-radius: 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 4px 12px rgba(0,0,0,0.15);
            overflow: hidden;
        }}
        .document-content {{
            padding: 40px;
            line-height: 1.8;
            color: #343a40;
        }}
        .document-title {{
            font-size: 24px;
            font-weight: 700;
            color: #212529;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 3px solid #339af0;
        }}
        .document-body {{
            font-size: 14px;
        }}
        .document-body p {{
            margin-bottom: 1em;
        }}
        .preview-badge {{
            display: inline-block;
            background: #fff9db;
            color: #f08c00;
            font-size: 11px;
            font-weight: 600;
            padding: 6px 12px;
            border-radius: 20px;
            margin-top: 30px;
        }}
    </style>
</head>
<body>
    <div class="document-container">
        <div class="metadata-bar">
            <span class="file-icon">{file_icon}</span>
            <span class="file-name">{file_name_escaped}</span>
            <span class="file-type">{file_type}</span>
        </div>
        <div class="paper-card">
            <div class="document-content">
                <h1 class="document-title">{title_escaped or "제목 없음"}</h1>
                <div class="document-body">
                    <p>{body_escaped or "(본문 내용이 비어있습니다)"}</p>
                </div>
                <div style="text-align: center;">
                    <span class="preview-badge">📄 미리보기 - 전체 문서의 일부만 표시됩니다</span>
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""
    
    def _show_loading_state(self) -> None:
        """로딩 상태 표시"""
        self.setHtml("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {
                    font-family: 'Segoe UI', sans-serif;
                    background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
                    height: 100vh;
                    margin: 0;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: #495057;
                }
                .container {
                    text-align: center;
                }
                .icon {
                    font-size: 64px;
                    margin-bottom: 20px;
                    opacity: 0.6;
                }
                .text {
                    font-size: 16px;
                    font-weight: 500;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="icon">📄</div>
                <div class="text">문서를 선택하면 미리보기가 표시됩니다</div>
            </div>
        </body>
        </html>
        """)
    
    def _show_error(self, message: str) -> None:
        """오류 표시"""
        self.setHtml(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: 'Segoe UI', sans-serif;
                    background: linear-gradient(135deg, #fff5f5 0%, #ffe3e3 100%);
                    height: 100vh;
                    margin: 0;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: #c92a2a;
                }}
                .container {{
                    text-align: center;
                }}
                .icon {{
                    font-size: 48px;
                    margin-bottom: 16px;
                }}
                .title {{
                    font-size: 18px;
                    font-weight: 600;
                    margin-bottom: 8px;
                }}
                .message {{
                    font-size: 14px;
                    max-width: 400px;
                    word-break: keep-all;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="icon">⚠️</div>
                <div class="title">미리보기를 생성할 수 없습니다</div>
                <div class="message">{html.escape(message)}</div>
            </div>
        </body>
        </html>
        """)
    
    def clear_preview(self) -> None:
        """미리보기 클리어"""
        self._show_loading_state()
    
    def cleanup(self) -> None:
        """정리 (특별히 정리할 것 없음)"""
        pass
