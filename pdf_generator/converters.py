import os
import shutil
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

import pymupdf
from PIL import Image, ImageOps


class ConversionError(Exception):
    pass


class EngineUnavailable(ConversionError):
    pass


def _office_app(prog_id, name):
    try:
        import pythoncom
        import win32com.client
        if prog_id in ('HWPFrame.HwpObject', 'PowerPoint.Application'):
            try:
                pythoncom.GetActiveObject(prog_id)
            except pythoncom.com_error:
                pass
            else:
                raise EngineUnavailable(f'{name}가 이미 실행 중입니다. 열린 문서를 보호하기 위해 변환을 시작하지 않습니다.')
        return win32com.client.DispatchEx(prog_id)
    except EngineUnavailable:
        raise
    except Exception as exc:
        raise EngineUnavailable(f'{name}를 사용할 수 없습니다. 설치 여부를 확인해 주세요.') from exc


class HwpConverter:
    engine = 'Hancom HWP'

    def convert(self, source, output):
        app = None
        try:
            app = _office_app('HWPFrame.HwpObject', '한컴오피스 한글')
            app.XHwpWindows.Item(0).Visible = False
            if not app.Open(str(source), '', ''):
                raise ConversionError('한컴오피스 한글에서 문서를 열 수 없습니다. 파일 형식을 확인해 주세요.')
            if not app.SaveAs(str(output), 'PDF'):
                raise ConversionError('한글에서 PDF 파일을 생성하지 못했습니다.')
        finally:
            if app is not None:
                try:
                    app.Clear(1)
                finally:
                    app.Quit()


class WordConverter:
    engine = 'Microsoft Word'

    def convert(self, source, output):
        app = _office_app('Word.Application', 'Microsoft Word')
        document = None
        try:
            app.Visible = False
            app.DisplayAlerts = 0
            app.AutomationSecurity = 3
            document = app.Documents.Open(str(source), ReadOnly=True, AddToRecentFiles=False,
                                          ConfirmConversions=False)
            document.ExportAsFixedFormat(str(output), 17)
        finally:
            try:
                if document is not None:
                    document.Close(False)
            finally:
                app.Quit()


class ExcelConverter:
    engine = 'Microsoft Excel'

    def convert(self, source, output):
        app = _office_app('Excel.Application', 'Microsoft Excel')
        workbook = None
        try:
            app.Visible = False
            app.DisplayAlerts = False
            app.AutomationSecurity = 3
            workbook = app.Workbooks.Open(str(source), UpdateLinks=0, ReadOnly=True,
                                          IgnoreReadOnlyRecommended=True)
            workbook.ExportAsFixedFormat(0, str(output))
        finally:
            try:
                if workbook is not None:
                    workbook.Close(False)
            finally:
                app.Quit()


class PowerPointConverter:
    engine = 'Microsoft PowerPoint'

    def convert(self, source, output):
        app = _office_app('PowerPoint.Application', 'Microsoft PowerPoint')
        presentation = None
        try:
            app.AutomationSecurity = 3
            presentation = app.Presentations.Open(str(source), ReadOnly=True, Untitled=False,
                                                  WithWindow=False)
            presentation.ExportAsFixedFormat(str(output), 2)
        finally:
            try:
                if presentation is not None:
                    presentation.Close()
            finally:
                app.Quit()


class LibreOfficeConverter:
    engine = 'LibreOffice'

    @staticmethod
    def executable():
        candidates = [shutil.which('soffice'),
                      r'C:\Program Files\LibreOffice\program\soffice.exe',
                      r'C:\Program Files (x86)\LibreOffice\program\soffice.exe']
        return next((path for path in candidates if path and Path(path).is_file()), None)

    def convert(self, source, output):
        executable = self.executable()
        if not executable:
            raise ConversionError('LibreOffice를 사용할 수 없습니다. 설치 여부를 확인해 주세요.')
        with tempfile.TemporaryDirectory(prefix='pdf_generator_lo_') as work:
            profile = Path(work) / 'profile'
            dest = Path(work) / 'output'
            dest.mkdir()
            command = [executable, f'-env:UserInstallation={profile.as_uri()}', '--headless',
                       '--convert-to', 'pdf', '--outdir', str(dest), str(source)]
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=180,
                                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            except subprocess.TimeoutExpired as exc:
                raise ConversionError('LibreOffice 변환 시간이 초과되었습니다.') from exc
            converted = dest / (Path(source).stem + '.pdf')
            if result.returncode or not converted.is_file():
                raise ConversionError('LibreOffice에서 PDF를 생성하지 못했습니다. 원본 파일을 확인해 주세요.')
            shutil.copyfile(converted, output)


class ImageConverter:
    engine = 'Image'

    def convert(self, source, output):
        pdf = pymupdf.open()
        try:
            with Image.open(source) as image:
                count = getattr(image, 'n_frames', 1)
                for index in range(count):
                    image.seek(index)
                    frame = ImageOps.exif_transpose(image).convert('RGB')
                    width, height = frame.size
                    if not width or not height:
                        raise ConversionError('이미지 크기가 올바르지 않습니다.')
                    stream = BytesIO()
                    frame.save(stream, format='PNG')
                    page = pdf.new_page(width=width, height=height)
                    page.insert_image(page.rect, stream=stream.getvalue())
            pdf.save(output)
        finally:
            pdf.close()


class TextConverter:
    engine = 'Local text'

    def convert(self, source, output):
        font_path = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Fonts' / 'malgun.ttf'
        if not font_path.is_file():
            return LibreOfficeConverter().convert(source, output)
        data = Path(source).read_bytes()
        encodings = ('utf-16',) if data.startswith((b'\xff\xfe', b'\xfe\xff')) else ('utf-8-sig', 'cp949')
        for encoding in encodings:
            try:
                text = data.decode(encoding)
                break
            except UnicodeError:
                continue
        else:
            raise ConversionError('텍스트 파일의 인코딩을 읽을 수 없습니다.')
        pdf = pymupdf.open()
        try:
            font = pymupdf.Font(fontfile=str(font_path))
            lines = []
            for line in text.splitlines() or ['']:
                line = line.expandtabs(4)
                while font.text_length(line, fontsize=10) > 515:
                    split = len(line)
                    while font.text_length(line[:split], fontsize=10) > 515:
                        split -= 1
                    lines.append(line[:split])
                    line = line[split:]
                lines.append(line)
            for start in range(0, len(lines), 52):
                page = pdf.new_page(width=595, height=842)
                page.insert_font(fontname='Malgun', fontfile=str(font_path))
                for offset, line in enumerate(lines[start:start + 52]):
                    page.insert_text((40, 50 + offset * 15), line, fontname='Malgun', fontsize=10)
            pdf.save(output)
        finally:
            pdf.close()
