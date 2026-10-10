import re
import unicodedata

from app.common.comparison_options import ComparisonOptions


def collect_raw_chars(raw_dict, page_num, excluded_bounds=None):
    chars = []
    for block_index, block in enumerate(raw_dict.get('blocks', [])):
        if excluded_bounds is not None and block.get('type') != 0:
            continue
        for line_index, line in enumerate(block.get('lines', [])):
            for span in line.get('spans', []):
                for char in span.get('chars', []):
                    bbox = char['bbox']
                    if excluded_bounds is not None:
                        top, bottom = excluded_bounds
                        if bbox[3] <= top or bbox[1] >= bottom:
                            continue
                    chars.append({
                        'char': unicodedata.normalize('NFC', char['c']),
                        'source_char': char['c'],
                        'line_id': (page_num, block_index, line_index),
                        'bbox': bbox, 'y': bbox[1], 'x': bbox[0], 'page': page_num,
                    })
    return chars


def normalize_raw_chars(raw_chars, page_aware=False, options=None):
    options = options or ComparisonOptions()
    if options.mode != 'body':
        return _normalize_with_options(raw_chars, page_aware, options)
    # Keep the legacy path unchanged, including whitelist and word IDs.
    if not raw_chars:
        return [], ''
    raw_chars.sort(key=(lambda char: (char['page'], char['y'])) if page_aware
                   else (lambda char: char['y']))
    grouped = []
    curr = [raw_chars[0]]
    for i in range(1, len(raw_chars)):
        if page_aware:
            same_line = (raw_chars[i]['page'] == curr[-1]['page']
                         and abs(raw_chars[i]['y'] - curr[-1]['y']) < 5.0)
        else:
            same_line = raw_chars[i]['y'] - curr[-1]['y'] < 5.0
        if same_line:
            curr.append(raw_chars[i])
        else:
            grouped.append(curr)
            curr = [raw_chars[i]]
    grouped.append(curr)

    final_norm = []
    raw_lines = []
    word_counter = 0
    for line in grouped:
        line.sort(key=lambda char: char['x'])
        line_str_raw = []
        word_counter += 1
        page_num = line[0]['page']
        for i, char in enumerate(line):
            line_str_raw.append(char['char'])
            if i > 0 and (line[i - 1]['char'].strip() == ''
                          or abs(char['x'] - line[i - 1]['bbox'][2]) > 2.5):
                word_counter += 1
            clean_char = char['char'].lower().strip()
            if not re.match(r'[가-힣a-z0-9.,?!;:()\-\[\]{}\'"]', clean_char):
                continue
            if not final_norm or not (clean_char == final_norm[-1]['char']
                                      and abs(char['x'] - final_norm[-1]['x']) < 2.5):
                final_norm.append({
                    'char': clean_char, 'bbox': char['bbox'], 'x': char['x'],
                    'y': char['y'], 'page': page_num, 'word_id': word_counter,
                })
        raw_lines.append(''.join(line_str_raw))
    return final_norm, '\n'.join(raw_lines)


def _normalize_with_options(raw_chars, page_aware, options):
    if not raw_chars:
        return [], ''
    if all('line_id' in char for char in raw_chars):
        line_map = {}
        for char in raw_chars:
            line_map.setdefault(char['line_id'], []).append(char)
        lines = sorted(line_map.values(), key=lambda line: (
            line[0]['page'] if page_aware else 0,
            min(char['y'] for char in line), min(char['x'] for char in line)))
    else:
        # Also support callers supplying raw glyphs without extraction metadata.
        lines = []
        for char in sorted(raw_chars, key=lambda c: (c['page'] if page_aware else 0, c['y'])):
            if (not lines or (page_aware and char['page'] != lines[-1][-1]['page'])
                    or abs(char['y'] - lines[-1][-1]['y']) >= 5.0):
                lines.append([])
            lines[-1].append(char)

    normalized, raw_lines = [], []
    word_id = 0
    previous_line = None
    for line in lines:
        line = sorted(line, key=lambda char: char['x'])
        if previous_line is not None and not options.ignore_line_breaks:
            word_id += 1
            previous = previous_line[-1]
            x0, y0, x1, y1 = previous['bbox']
            # A PDF has no newline glyph. Anchor its marker at the preceding line end.
            normalized.append({**previous, 'char': '\n', 'source_char': '\n',
                               'bbox': (max(x0, x1 - 2), y0, x1, y1),
                               'word_id': word_id, 'synthetic': True})
        word_id += 1
        raw_lines.append(''.join(char.get('source_char', char['char']) for char in line))
        for index, glyph in enumerate(line):
            source = glyph.get('source_char', glyph['char'])
            if index and (line[index - 1].get('source_char', line[index - 1]['char']).isspace()
                          or abs(glyph['x'] - line[index - 1]['bbox'][2]) > 2.5):
                word_id += 1
            for character in source:
                is_newline = character in '\r\n\u2028\u2029'
                if is_newline and options.ignore_line_breaks:
                    continue
                if character.isspace() and not is_newline and options.ignore_spaces:
                    continue
                if options.ignore_symbols and unicodedata.category(character)[0] in ('P', 'S'):
                    continue
                value = character.lower() if options.ignore_case else character
                # One record per code point keeps diff offsets and highlight positions aligned.
                for codepoint in value:
                    normalized.append({**glyph, 'char': codepoint,
                                       'source_char': source, 'word_id': word_id})
        previous_line = line
    return normalized, '\n'.join(raw_lines)
