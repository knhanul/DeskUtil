import logging
import os
import tempfile
from pathlib import Path

import pymupdf

from .converters import (ConversionError, EngineUnavailable, ExcelConverter, HwpConverter,
                         ImageConverter, LibreOfficeConverter, PowerPointConverter,
                         TextConverter, WordConverter)

SUPPORTED_EXTENSIONS = {
    '.hwp': HwpConverter, '.hwpx': HwpConverter,
    '.doc': WordConverter, '.docx': WordConverter,
    '.xls': ExcelConverter, '.xlsx': ExcelConverter,
    '.ppt': PowerPointConverter, '.pptx': PowerPointConverter,
    '.odt': LibreOfficeConverter, '.ods': LibreOfficeConverter, '.odp': LibreOfficeConverter,
    '.txt': TextConverter, '.rtf': WordConverter,
    '.jpg': ImageConverter, '.jpeg': ImageConverter, '.png': ImageConverter,
    '.bmp': ImageConverter, '.tif': ImageConverter, '.tiff': ImageConverter,
}


def _logger():
    logger = logging.getLogger('pdf_generator')
    if not logger.handlers:
        log_dir = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'DeskUtil'
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(log_dir / 'pdf_generator.log', encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def validate_pdf(path):
    if not path.is_file() or path.stat().st_size == 0:
        raise ConversionError('PDF 파일이 생성되지 않았습니다. 출력 폴더의 쓰기 권한을 확인해 주세요.')
    try:
        with pymupdf.open(stream=path.read_bytes(), filetype='pdf') as pdf:
            if pdf.page_count < 1 or pdf.is_repaired:
                raise ConversionError('생성된 PDF가 정상적이지 않습니다.')
    except (pymupdf.FileDataError, pymupdf.EmptyFileError) as exc:
        raise ConversionError('생성된 PDF가 정상적이지 않습니다.') from exc


class ConverterManager:
    def convert_to_pdf(self, source_path, output_dir):
        source = Path(source_path).resolve()
        suffix = source.suffix.lower()
        if suffix == '.pdf':
            raise ConversionError('이미 PDF 형식의 파일입니다.')
        converter_type = SUPPORTED_EXTENSIONS.get(suffix)
        if not converter_type:
            raise ConversionError(f'지원하지 않는 파일 형식입니다: {suffix or "(확장자 없음)"}')
        if not source.is_file():
            raise ConversionError('원본 파일을 찾을 수 없습니다.')
        output_dir = Path(output_dir).resolve()
        if not output_dir.is_dir():
            raise ConversionError('출력 폴더를 찾을 수 없습니다. 출력 위치를 확인해 주세요.')
        logger = _logger()
        fd, temp_name = tempfile.mkstemp(prefix='.pdf_generator_', suffix='.pdf', dir=output_dir)
        os.close(fd)
        temp = Path(temp_name)
        temp.unlink()
        converter = converter_type()
        try:
            try:
                converter.convert(source, temp)
            except EngineUnavailable:
                if converter_type is LibreOfficeConverter or not LibreOfficeConverter.executable():
                    raise
                converter = LibreOfficeConverter()
                converter.convert(source, temp)
            validate_pdf(temp)
            destination = output_dir / f'{source.stem}.pdf'
            index = 0
            while True:
                try:
                    os.link(temp, destination)
                    break
                except FileExistsError:
                    index += 1
                    destination = output_dir / f'{source.stem} ({index}).pdf'
            logger.info('SOURCE=%s TYPE=%s ENGINE=%s RESULT=SUCCESS OUTPUT=%s',
                        source, suffix, converter.engine, destination)
            return destination
        except Exception as exc:
            logger.exception('SOURCE=%s TYPE=%s ENGINE=%s RESULT=FAILURE ERROR=%s',
                             source, suffix, converter.engine, type(exc).__name__)
            if isinstance(exc, ConversionError):
                raise
            raise ConversionError('PDF 생성에 실패했습니다. 원본 파일과 출력 폴더를 확인해 주세요.') from exc
        finally:
            temp.unlink(missing_ok=True)
