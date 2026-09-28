import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pymupdf
from PIL import Image

from pdf_generator import ConverterManager, ConversionError
from pdf_generator.manager import validate_pdf


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / 'output'
        self.output.mkdir()
        self.manager = ConverterManager()

    def test_image_conversion_and_validation(self):
        source = self.root / 'image.png'
        Image.new('RGB', (120, 60), (255, 0, 0)).save(source)
        result = self.manager.convert_to_pdf(source, self.output)
        validate_pdf(result)
        with pymupdf.open(result) as pdf:
            self.assertEqual(pdf.page_count, 1)
            self.assertEqual((pdf[0].rect.width, pdf[0].rect.height), (120, 60))
        with Image.open(source) as image:
            self.assertEqual(image.size, (120, 60))

    def test_jpeg_and_bmp_conversion(self):
        for extension in ('.jpg', '.jpeg', '.bmp'):
            with self.subTest(extension=extension):
                source = self.root / ('image' + extension)
                Image.new('RGB', (90, 45)).save(source)
                with pymupdf.open(self.manager.convert_to_pdf(source, self.output)) as pdf:
                    self.assertEqual(pdf.page_count, 1)
                    self.assertEqual((pdf[0].rect.width, pdf[0].rect.height), (90, 45))

    def test_collision_never_overwrites(self):
        source = self.root / 'image.png'
        Image.new('RGB', (32, 32)).save(source)
        existing = self.output / 'image.pdf'
        existing.write_bytes(b'unchanged')
        first = self.manager.convert_to_pdf(source, self.output)
        second = self.manager.convert_to_pdf(source, self.output)
        self.assertEqual(existing.read_bytes(), b'unchanged')
        self.assertEqual((first.name, second.name), ('image (1).pdf', 'image (2).pdf'))

    def test_text_and_multipage_tiff(self):
        source = self.root / '한글.txt'
        source.write_text('안녕하세요 PDF 생성', encoding='utf-8')
        try:
            text_pdf = self.manager.convert_to_pdf(source, self.output)
        except ConversionError as exc:
            if 'LibreOffice를 사용할 수 없습니다' in str(exc):
                self.skipTest('한국어 글꼴 및 LibreOffice가 없음')
            raise
        with pymupdf.open(text_pdf) as pdf:
            self.assertIn('안녕하세요 PDF 생성', pdf[0].get_text())
        source = self.root / 'pages.tiff'
        first = Image.new('RGB', (80, 40))
        second = Image.new('RGB', (40, 80))
        first.save(source, save_all=True, append_images=[second])
        with pymupdf.open(self.manager.convert_to_pdf(source, self.output)) as pdf:
            self.assertEqual(pdf.page_count, 2)
            self.assertEqual((pdf[1].rect.width, pdf[1].rect.height), (40, 80))

    def test_invalid_and_pdf_inputs(self):
        for suffix, expected in (('.pdf', '이미 PDF'), ('.zip', '지원하지 않는')):
            source = self.root / ('input' + suffix)
            source.write_text('content')
            with self.assertRaisesRegex(ConversionError, expected):
                self.manager.convert_to_pdf(source, self.output)

    def test_invalid_export_does_not_leave_file(self):
        source = self.root / 'input.docx'
        source.write_text('content')
        with patch('pdf_generator.manager.WordConverter.convert', lambda self, src, dst: Path(dst).write_bytes(b'invalid')):
            with self.assertRaises(ConversionError):
                self.manager.convert_to_pdf(source, self.output)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_engine_selection(self):
        from pdf_generator.manager import SUPPORTED_EXTENSIONS
        for suffix, engine in (('.hwp', 'HwpConverter'), ('.hwpx', 'HwpConverter'),
                               ('.doc', 'WordConverter'), ('.xlsx', 'ExcelConverter'),
                               ('.pptx', 'PowerPointConverter'), ('.odt', 'LibreOfficeConverter'),
                               ('.rtf', 'WordConverter'), ('.tiff', 'ImageConverter')):
            self.assertEqual(SUPPORTED_EXTENSIONS[suffix].__name__, engine)

    def test_office_cleanup_on_export_failure(self):
        from pdf_generator.converters import (ExcelConverter, HwpConverter,
                                              PowerPointConverter, WordConverter)
        for converter_type, document in ((HwpConverter, None), (WordConverter, 'Documents'),
                                         (ExcelConverter, 'Workbooks'), (PowerPointConverter, 'Presentations')):
            with self.subTest(converter=converter_type.__name__):
                app = MagicMock()
                app.Open.return_value = True
                if document == 'Documents':
                    app.Documents.Open.return_value.ExportAsFixedFormat.side_effect = RuntimeError('fail')
                elif document == 'Workbooks':
                    app.Workbooks.Open.return_value.ExportAsFixedFormat.side_effect = RuntimeError('fail')
                elif document == 'Presentations':
                    app.Presentations.Open.return_value.ExportAsFixedFormat.side_effect = RuntimeError('fail')
                else:
                    app.SaveAs.side_effect = RuntimeError('fail')
                with patch('pdf_generator.converters._office_app', return_value=app):
                    with self.assertRaises(RuntimeError):
                        converter_type().convert(self.root / 'source', self.output / 'result.pdf')
                app.Quit.assert_called_once()
                if document:
                    getattr(app, document).Open.return_value.Close.assert_called_once()
                else:
                    app.Clear.assert_called_once()

    def test_batch_keeps_running_after_one_file_fails(self):
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        from PyQt6.QtCore import QEventLoop, QTimer
        from PyQt6.QtWidgets import QApplication
        from app.tools.pdf_generator_ui import PdfGeneratorWidget
        app = QApplication.instance() or QApplication([])
        image = self.root / 'good.png'
        Image.new('RGB', (50, 25)).save(image)
        bad = self.root / 'bad.docx'
        bad.write_bytes(b'not a document')
        widget = PdfGeneratorWidget()
        widget.add_files([str(bad), str(image)])
        widget.folder_edit.setText(str(self.output))
        with patch('pdf_generator.manager.WordConverter.convert', side_effect=ConversionError('테스트 실패')):
            widget.start_conversion()
            loop = QEventLoop()
            widget.worker.finished.connect(loop.quit)
            QTimer.singleShot(10000, loop.quit)
            loop.exec()
            app.processEvents()
        self.assertEqual([widget.table.item(row, 2).text() for row in range(2)], ['실패', '완료'])
        self.assertTrue((self.output / 'good.pdf').exists())
        widget.close()

    def test_menu_order_and_other_tools_remain_available(self):
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        from PyQt6.QtWidgets import QApplication
        from app.main_window import MdiMainWindow
        app = QApplication.instance() or QApplication([])
        window = MdiMainWindow()
        self.assertEqual([tool['menu_title'] for tool in window.tool_definitions],
                         ['영역지정비교', '전체비교', 'PDF 생성', '문서찾기'])
        for key in ('pdf_compare', 'pdf_hf_compare', 'pdf_generator', 'document_search'):
            window.open_tool(key)
            self.assertEqual(window.current_tool_key, key)
        window.close()


if __name__ == '__main__':
    unittest.main()
