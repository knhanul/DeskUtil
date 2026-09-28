import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pymupdf
from PyQt6.QtCore import QRect
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication

from app.common.pdf_compare_worker import PdfCompareWorker
from app.common.pdf_text_normalizer import collect_raw_chars, normalize_raw_chars
from app.tools.pdf_compare import PDFViewer, PdfCompareWidget
from app.tools.pdf_header_footer_compare import HFCompareWidget, HFViewer


class MultiPageSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def make_pdf(self, name, texts):
        path = Path(self.temp.name) / name
        pdf = pymupdf.open()
        for text in texts:
            page = pdf.new_page(width=300, height=400)
            page.insert_text((40, 75), text, fontsize=16)
        pdf.save(path)
        pdf.close()
        return path

    def select(self, viewer, page):
        viewer.on_selection_complete(page, QRect(30, 55, 260, 110))

    def test_shared_normalization_preserves_filtering_and_word_ids(self):
        characters = [('A', 10), ('A', 10.5), (' ', 14), ('B', 18),
                      ('?', 22), ('\t', 26), ('C', 30), ('e\u0301', 34)]
        raw_dict = {'blocks': [
            {'type': 0, 'lines': [{'spans': [{'chars': [
                {'c': character, 'bbox': (x, 10, x + 2, 18)} for character, x in characters
            ]}]}]},
            {'type': 1, 'lines': [{'spans': [{'chars': [
                {'c': 'Z', 'bbox': (40, 10, 42, 18)}
            ]}]}]},
        ]}
        area_chars, area_raw = normalize_raw_chars(collect_raw_chars(raw_dict, 0))
        self.assertEqual(''.join(char['char'] for char in area_chars), 'ab?cz')
        self.assertEqual(area_raw, 'AA B?\tCéZ')
        self.assertEqual([char['word_id'] for char in area_chars], [1, 2, 2, 3, 4])
        full_chars, full_raw = normalize_raw_chars(
            collect_raw_chars(raw_dict, 0, excluded_bounds=(0, 100)), page_aware=True
        )
        self.assertEqual(''.join(char['char'] for char in full_chars), 'ab?c')
        self.assertEqual(full_raw, 'AA B?\tCé')
        self.assertEqual([char['word_id'] for char in full_chars], [1, 2, 2, 3])
        self.assertEqual(collect_raw_chars(raw_dict, 0, excluded_bounds=(18, 100)), [])
        self.assertEqual(normalize_raw_chars([]), ([], ''))

    def test_area_and_full_text_extraction_contract(self):
        path = Path(self.temp.name) / 'contract.pdf'
        pdf = pymupdf.open()
        for body in ('Alpha (1)', 'Beta - XYZ'):
            page = pdf.new_page(width=300, height=400)
            page.insert_text((40, 15), 'HEAD', fontsize=10)
            page.insert_text((40, 75), body, fontsize=16)
        pdf.save(path)
        pdf.close()
        area = PDFViewer()
        full = HFViewer()
        self.assertTrue(area.load_pdf(path))
        self.addCleanup(area.pdf_doc.close)
        self.assertTrue(full.load_pdf(path))
        self.addCleanup(full.pdf_doc.close)
        chars, raw = area.extract_and_process_text(0, QRect(30, 55, 280, 100))
        self.assertEqual(''.join(char['char'] for char in chars), 'alpha(1)')
        self.assertEqual(raw, 'Alpha (1)')
        self.assertEqual({char['page'] for char in chars}, {0})
        full.extract_body_text()
        self.assertEqual(''.join(char['char'] for char in full.char_data), 'alpha(1)beta-xyz')
        self.assertEqual(full.raw_text, 'Alpha (1)\nBeta - XYZ')
        self.assertEqual({char['page'] for char in full.char_data}, {0, 1})
        self.assertEqual([(char['char'], char['word_id']) for char in chars],
                         [(char['char'], char['word_id']) for char in full.char_data if char['page'] == 0])
        full.header_ratio = 0
        full.extract_body_text()
        self.assertIn('head', ''.join(char['char'] for char in full.char_data))
        area.close()
        full.close()

    def test_single_selection_and_navigation_keep_previous_page(self):
        viewer = PDFViewer()
        self.assertTrue(viewer.load_pdf(self.make_pdf('a.pdf', ['First', 'Second', 'Third'])))
        self.addCleanup(viewer.pdf_doc.close)
        self.select(viewer, 1)
        viewer.goto_page(3)
        self.select(viewer, 0)
        self.assertEqual(set(viewer.selection_areas), {0, 1})
        self.assertEqual(''.join(c['char'] for c in viewer.char_data), 'firstsecond')
        self.assertEqual(set(viewer.last_compared_area), {0, 1})
        self.assertEqual({c['page'] for c in viewer.char_data}, {0, 1})
        self.assertEqual(len({c['word_id'] for c in viewer.char_data}), 2)
        viewer.zoom_in()
        self.assertEqual(set(viewer.last_compared_area), {0, 1})
        viewer.clear_all_data()
        self.assertFalse(viewer.selection_areas)
        self.assertIsNone(viewer.pending_selection_rect)
        self.assertFalse(viewer.char_data)
        viewer.close()

    def test_multiple_regions_same_page_and_cross_pdf_page_numbers(self):
        left = PDFViewer()
        right = PDFViewer()
        self.assertTrue(left.load_pdf(self.make_pdf('left.pdf', ['Match', 'Left'])))
        self.addCleanup(left.pdf_doc.close)
        self.assertTrue(right.load_pdf(self.make_pdf('right.pdf', ['Skip', 'Match', 'Right'])))
        self.addCleanup(right.pdf_doc.close)
        self.select(left, 0)
        self.select(right, 1)
        self.assertEqual(''.join(c['char'] for c in left.char_data), 'match')
        self.assertEqual(''.join(c['char'] for c in right.char_data), 'match')
        self.select(left, 1)
        self.select(right, 2)
        self.assertEqual(len(left.selection_areas), 2)
        self.select(left, 1)
        self.assertEqual(len(left.selection_areas[1]), 2)
        self.assertEqual(len({c['word_id'] for c in left.char_data}), 3)
        results = []
        worker = PdfCompareWorker(left.char_data, right.char_data, left.raw_text, right.raw_text,
                                  left.pending_selection_rect, right.pending_selection_rect)
        worker.result_ready.connect(results.append)
        worker.run()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['s1_norm'], 'matchleftleft')
        self.assertEqual(results[0]['s2_norm'], 'matchright')
        self.assertTrue(results[0]['diff_pages1'])
        left.close()
        right.close()

    def test_widget_comparison_reports_differences_on_selected_pages(self):
        from PyQt6.QtCore import QEventLoop, QTimer
        widget = PdfCompareWidget()
        self.assertTrue(widget.viewer1.load_pdf(self.make_pdf('compare1.pdf', ['Match', 'Left'])))
        self.addCleanup(widget.viewer1.pdf_doc.close)
        self.assertTrue(widget.viewer2.load_pdf(self.make_pdf('compare2.pdf', ['Skip', 'Match', 'Right'])))
        self.addCleanup(widget.viewer2.pdf_doc.close)
        self.select(widget.viewer1, 0)
        self.select(widget.viewer1, 1)
        self.select(widget.viewer2, 1)
        self.select(widget.viewer2, 2)
        widget.btn_compare.click()
        loop = QEventLoop()
        widget.compare_manager.result_ready.connect(loop.quit)
        QTimer.singleShot(3000, loop.quit)
        loop.exec()
        self.assertEqual(widget.last_s1_norm, 'matchleft')
        self.assertEqual(widget.last_s2_norm, 'matchright')
        self.assertEqual({item['page'] for item in widget.diff_list if item['pdf'] == 'PDF 1'}, {2})
        self.assertEqual({item['page'] for item in widget.diff_list if item['pdf'] == 'PDF 2'}, {3})
        loop = QEventLoop()
        QTimer.singleShot(200, loop.quit)
        loop.exec()
        widget.close()

    def test_full_compare_scroll_stays_continuous_before_comparison(self):
        from PyQt6.QtCore import QEventLoop, QTimer
        widget = HFCompareWidget()
        texts = ['First', 'Second', 'Third']
        self.assertTrue(widget.viewer1.load_pdf(self.make_pdf('scroll1.pdf', texts)))
        self.addCleanup(widget.viewer1.pdf_doc.close)
        self.assertTrue(widget.viewer2.load_pdf(self.make_pdf('scroll2.pdf', texts)))
        self.addCleanup(widget.viewer2.pdf_doc.close)
        widget.resize(1200, 700)
        widget.show()
        loop = QEventLoop()
        QTimer.singleShot(150, loop.quit)
        loop.exec()
        widget.viewer1.verticalScrollBar().setValue(180)
        widget.sync_scroll_cb.setChecked(True)
        self.assertLess(abs(widget.viewer2.verticalScrollBar().value() - 180), 30)
        widget.viewer1.verticalScrollBar().setValue(100)
        first = widget.viewer2.verticalScrollBar().value()
        widget.viewer1.verticalScrollBar().setValue(140)
        second = widget.viewer2.verticalScrollBar().value()
        self.assertGreater(second, first)
        self.assertLess(abs(second - 140), 30)
        widget.viewer2.verticalScrollBar().setValue(250)
        self.assertLess(abs(widget.viewer1.verticalScrollBar().value() - 250), 30)
        widget.close()

    def test_full_compare_scroll_without_matches_tracks_document_progress(self):
        from PyQt6.QtCore import QEventLoop, QTimer
        widget = HFCompareWidget()
        self.assertTrue(widget.viewer1.load_pdf(self.make_pdf('short.pdf', ['A', 'B'])))
        self.addCleanup(widget.viewer1.pdf_doc.close)
        self.assertTrue(widget.viewer2.load_pdf(self.make_pdf('long.pdf', ['A', 'B', 'C', 'D'])))
        self.addCleanup(widget.viewer2.pdf_doc.close)
        widget.resize(1200, 700)
        widget.show()
        loop = QEventLoop()
        QTimer.singleShot(150, loop.quit)
        loop.exec()
        widget.sync_scroll_cb.setChecked(True)
        source = widget.viewer1.verticalScrollBar()
        target = widget.viewer2.verticalScrollBar()
        source.setValue(source.maximum() // 2)
        self.assertLess(abs(target.value() / target.maximum() - 0.5), 0.05)
        target.setValue(target.maximum() * 3 // 4)
        self.assertLess(abs(source.value() / source.maximum() - 0.75), 0.05)
        widget.close()

    def test_full_compare_scroll_aligns_matching_pages_after_comparison(self):
        from PyQt6.QtCore import QEventLoop, QTimer
        widget = HFCompareWidget()
        self.assertTrue(widget.viewer1.load_pdf(self.make_pdf('match1.pdf', ['Alpha', 'Bravo', 'Charlie'])))
        self.addCleanup(widget.viewer1.pdf_doc.close)
        self.assertTrue(widget.viewer2.load_pdf(self.make_pdf('match2.pdf', ['Cover', 'Alpha', 'Bravo', 'Charlie'])))
        self.addCleanup(widget.viewer2.pdf_doc.close)
        widget.resize(1200, 700)
        widget.show()
        loop = QEventLoop()
        QTimer.singleShot(150, loop.quit)
        loop.exec()
        for viewer in (widget.viewer1, widget.viewer2):
            viewer.extract_body_text()
        from app.common.pdf_compare_worker import PdfCompareWorker
        results = []
        worker = PdfCompareWorker(widget.viewer1.char_data, widget.viewer2.char_data,
                                  widget.viewer1.raw_text, widget.viewer2.raw_text)
        worker.result_ready.connect(results.append)
        worker.run()
        with patch.object(widget, '_refresh_viewers_optimized'):
            widget._on_compare_result_ready(results[0])
        widget.sync_scroll_cb.setChecked(True)
        widget.viewer1.verticalScrollBar().setValue(widget.viewer1.page_labels[1].y() + 100)
        self.assertEqual(widget.get_current_page(widget.viewer2), 2)
        widget.viewer2.verticalScrollBar().setValue(widget.viewer2.page_labels[1].y() + 100)
        self.assertEqual(widget.get_current_page(widget.viewer1), 0)
        widget.viewer2.zoom_in()
        loop = QEventLoop()
        QTimer.singleShot(150, loop.quit)
        loop.exec()
        widget.viewer1.verticalScrollBar().setValue(widget.viewer1.page_labels[2].y() + 90)
        self.assertEqual(widget.get_current_page(widget.viewer2), 3)
        widget.close()

    def test_full_compare_can_compare_again_after_page_reset(self):
        from PyQt6.QtCore import QEventLoop, QTimer
        widget = HFCompareWidget()
        self.assertTrue(widget.viewer1.load_pdf(self.make_pdf('again1.pdf', ['Same', 'Left'])))
        self.addCleanup(widget.viewer1.pdf_doc.close)
        self.assertTrue(widget.viewer2.load_pdf(self.make_pdf('again2.pdf', ['Same', 'Right'])))
        self.addCleanup(widget.viewer2.pdf_doc.close)

        def compare():
            widget.viewer1.extract_body_text()
            widget.viewer2.extract_body_text()
            self.assertTrue(widget.viewer1.char_data)
            self.assertTrue(widget.viewer2.char_data)
            widget.start_async_comparison()
            loop = QEventLoop()
            widget.compare_manager.result_ready.connect(loop.quit)
            QTimer.singleShot(3000, loop.quit)
            loop.exec()
            self.assertEqual(widget.last_s1_norm, 'sameleft')
            self.assertEqual(widget.last_s2_norm, 'sameright')
            loop = QEventLoop()
            QTimer.singleShot(150, loop.quit)
            loop.exec()

        with patch('app.tools.pdf_header_footer_compare.QMessageBox.information'):
            compare()
            widget.get_current_page = lambda viewer: 1
            widget.btn_reset_page.click()
            self.assertNotIn(1, widget.viewer1.word_highlights)
            self.assertNotIn(1, widget.viewer2.word_highlights)
            compare()
            self.assertIn(1, widget.viewer1.word_highlights)
            self.assertIn(1, widget.viewer2.word_highlights)
        widget.close()

    def test_full_compare_reset_uses_each_viewers_visible_page(self):
        from PyQt6.QtCore import QEventLoop, QTimer
        widget = HFCompareWidget()
        self.assertTrue(widget.viewer1.load_pdf(self.make_pdf('visible1.pdf', ['One', 'Two', 'Three'])))
        self.addCleanup(widget.viewer1.pdf_doc.close)
        self.assertTrue(widget.viewer2.load_pdf(self.make_pdf('visible2.pdf', ['One', 'Two', 'Three'])))
        self.addCleanup(widget.viewer2.pdf_doc.close)
        widget.resize(1200, 700)
        widget.show()
        loop = QEventLoop()
        QTimer.singleShot(150, loop.quit)
        loop.exec()
        widget.viewer1.goto_page(2)
        widget.viewer2.goto_page(3)
        self.app.processEvents()
        self.assertEqual(widget.get_current_page(widget.viewer1), 1)
        self.assertEqual(widget.get_current_page(widget.viewer2), 2)
        for viewer in (widget.viewer1, widget.viewer2):
            viewer.last_compared_area = {page: [(40, 50, 100, 80)] for page in range(3)}
        widget.btn_reset_page.click()
        self.assertEqual(set(widget.viewer1.last_compared_area), {0, 2})
        self.assertEqual(set(widget.viewer2.last_compared_area), {0, 1})
        widget.close()

    def test_full_compare_page_reset_preserves_other_page_results(self):
        widget = HFCompareWidget()
        self.assertTrue(widget.viewer1.load_pdf(self.make_pdf('full1.pdf', ['First', 'Second', 'Third'])))
        self.addCleanup(widget.viewer1.pdf_doc.close)
        self.assertTrue(widget.viewer2.load_pdf(self.make_pdf('full2.pdf', ['First', 'Second', 'Third'])))
        self.addCleanup(widget.viewer2.pdf_doc.close)
        self.assertIn('페이지 초기화', widget.btn_reset_page.text())
        for viewer in (widget.viewer1, widget.viewer2):
            viewer.word_highlights = {page: [((40, 50, 100, 80), QColor(255, 0, 0))] for page in range(3)}
            viewer.last_compared_area = {page: [(40, 50, 100, 80)] for page in range(3)}
            viewer.diff_pages = [(page, 60) for page in range(3)]
            viewer.diff_index = 1
        widget.diff_list = [
            {'pdf': 'PDF 1', 'page': page + 1} for page in range(3)
        ] + [{'pdf': 'PDF 2', 'page': page + 1} for page in range(3)]
        widget.sync_anchor_pairs = [((0, 60), (0, 60)), ((1, 60), (2, 60))]
        widget.viewer1.header_ratio = 0.1
        widget.viewer2.footer_ratio = 0.12
        widget.get_current_page = lambda viewer: 1 if viewer is widget.viewer1 else 2
        widget.reset_current_page()
        self.assertEqual(set(widget.viewer1.word_highlights), {0, 2})
        self.assertEqual(set(widget.viewer2.word_highlights), {0, 1})
        self.assertEqual(set(widget.viewer1.last_compared_area), {0, 2})
        self.assertEqual(set(widget.viewer2.last_compared_area), {0, 1})
        self.assertEqual(widget.viewer1.diff_pages, [(0, 60), (2, 60)])
        self.assertEqual(widget.viewer2.diff_pages, [(0, 60), (1, 60)])
        self.assertEqual(widget.viewer1.diff_index, -1)
        self.assertEqual(widget.viewer2.diff_index, -1)
        self.assertEqual(widget.diff_list, [
            {'pdf': 'PDF 1', 'page': 1}, {'pdf': 'PDF 1', 'page': 3},
            {'pdf': 'PDF 2', 'page': 1}, {'pdf': 'PDF 2', 'page': 2},
        ])
        self.assertEqual(widget.sync_anchor_pairs, [((0, 60), (0, 60))])
        self.assertEqual(widget.viewer1.header_ratio, 0.1)
        self.assertEqual(widget.viewer2.footer_ratio, 0.12)
        widget.close()

    def test_page_reset_keeps_other_page_selection(self):
        widget = PdfCompareWidget()
        self.assertTrue(widget.viewer1.load_pdf(self.make_pdf('reset1.pdf', ['First', 'Second'])))
        self.addCleanup(widget.viewer1.pdf_doc.close)
        self.assertTrue(widget.viewer2.load_pdf(self.make_pdf('reset2.pdf', ['First', 'Second'])))
        self.addCleanup(widget.viewer2.pdf_doc.close)
        self.select(widget.viewer1, 0)
        self.select(widget.viewer1, 1)
        self.select(widget.viewer2, 0)
        self.select(widget.viewer2, 1)
        widget.get_current_page = lambda viewer: 1
        widget._do_reset_current_page(0)
        from PyQt6.QtCore import QEventLoop, QTimer
        loop = QEventLoop()
        QTimer.singleShot(150, loop.quit)
        loop.exec()
        for viewer in (widget.viewer1, widget.viewer2):
            self.assertEqual(set(viewer.selection_areas), {0})
            self.assertEqual(''.join(c['char'] for c in viewer.char_data), 'first')
            self.assertEqual(viewer.pending_selection_rect[0], 0)
        widget._do_reset_all(0)
        loop = QEventLoop()
        QTimer.singleShot(150, loop.quit)
        loop.exec()
        for viewer in (widget.viewer1, widget.viewer2):
            self.assertFalse(viewer.selection_areas)
            self.assertIsNone(viewer.pending_selection_rect)
            self.assertFalse(viewer.char_data)
        widget.close()


if __name__ == '__main__':
    unittest.main()
