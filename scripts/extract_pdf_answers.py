"""
公職王 PDF 答案提取器
從 data/pdfs/ 下的 PDF 提取選擇題答案
執行：python scripts/extract_pdf_answers.py
輸出：data/pdf_answers.json
"""
import json
import zlib
import re
import hashlib
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

try:
    import pikepdf
except ImportError:
    print("請執行: pip install pikepdf")
    sys.exit(1)

# 已知答案圖片雜湊 → 字母映射 (從 113年行政法概要 PDF 建立)
ANSWER_HASHES: dict[str, str] = {
    'b85cfa95a61d17c653a3966028d69e71': 'D',
    '3609ba45be8dd729c06e1a4ac93cbd8a': 'A',
    '3982d818f7ca9bd991956019b7378780': 'B',
    '45bd951c9c309bffb0b5a16f5ca4722d': 'C',
}

DATA_DIR = Path(__file__).parent.parent / 'data'
PDF_DIR = DATA_DIR / 'pdfs'
OUTPUT_FILE = DATA_DIR / 'pdf_answers.json'


def get_smask_hash(pdf: pikepdf.Pdf, xobj: pikepdf.Object) -> str | None:
    smask = xobj.get('/SMask')
    if not smask:
        return None
    smask_obj = pdf.get_object(smask.objgen) if hasattr(smask, 'objgen') else smask
    raw = bytes(smask_obj.read_raw_bytes())
    return hashlib.md5(raw).hexdigest()


def read_stream_bytes(stream_obj, pdf: pikepdf.Pdf) -> bytes:
    """讀取 content stream 位元組，自動解壓縮"""
    try:
        raw = bytes(stream_obj.read_raw_bytes())
        try:
            return zlib.decompress(raw)
        except Exception:
            return raw
    except Exception:
        return b''


def extract_answers_from_pdf(pdf_path: Path) -> list[str]:
    """從一份 PDF 提取所有選擇題答案，回傳答案字母清單（順序即題序）"""
    pdf = pikepdf.open(pdf_path)
    all_answers: list[tuple[int, float, float, str]] = []  # (page, y, question_seq, letter)

    for page_idx, page in enumerate(pdf.pages):
        resources = page.get('/Resources')
        if not resources:
            continue
        xobjects = resources.get('/XObject', {})

        contents_obj = page.get('/Contents')
        if contents_obj is None:
            continue

        # 讀取所有 content streams
        all_text = ''
        try:
            # 嘗試作為單一 stream
            raw = bytes(contents_obj.read_raw_bytes())
            try:
                all_text = zlib.decompress(raw).decode('latin-1', errors='replace')
            except Exception:
                all_text = raw.decode('latin-1', errors='replace')
        except Exception:
            # 作為 stream 陣列
            try:
                for cs in contents_obj:
                    if hasattr(cs, 'read_raw_bytes'):
                        data = read_stream_bytes(cs, pdf)
                        all_text += data.decode('latin-1', errors='replace')
            except Exception:
                pass

        # 找答案圖片（x≈48）
        answer_imgs: list[tuple[float, str]] = []  # (y, img_name)
        for m in re.finditer(
            r'([\d.]+) 0 0 ([\d.]+) ([\d.]+) ([\d.]+) cm[\r\n]+/(\w+) Do',
            all_text
        ):
            w = float(m.group(1))
            x = float(m.group(3))
            y = float(m.group(4))
            img_name = m.group(5)
            if w < 25 and 44 <= x <= 52:
                answer_imgs.append((y, img_name))

        answer_imgs.sort(key=lambda t: -t[0])  # 由上而下

        for y, img_name in answer_imgs:
            xobj_ref = xobjects.get('/' + img_name)
            if not xobj_ref:
                continue
            try:
                xobj = pdf.get_object(xobj_ref.objgen) if hasattr(xobj_ref, 'objgen') else xobj_ref
                h = get_smask_hash(pdf, xobj)
                letter = ANSWER_HASHES.get(h, '?') if h else '?'
                all_answers.append((page_idx, y, len(all_answers), letter))
            except Exception:
                pass

    # 排序：先 page，再 y 降序
    all_answers.sort(key=lambda t: (t[0], -t[1]))
    return [letter for _, _, _, letter in all_answers]


def run():
    print('=== 公職王 PDF 答案提取器 ===')
    
    # 找所有 PDF
    pdfs = sorted(PDF_DIR.glob('*.pdf'))
    print(f'找到 {len(pdfs)} 個 PDF')
    
    results = {}
    
    for pdf_path in pdfs:
        fname = pdf_path.stem  # e.g. '113_行政法概要'
        parts = fname.split('_', 1)
        if len(parts) < 2:
            continue
        roc_year_str, subject = parts[0], parts[1]
        try:
            roc_year = int(roc_year_str)
        except ValueError:
            continue
        
        print(f'\n處理：{fname}.pdf')
        answers = extract_answers_from_pdf(pdf_path)
        print(f'  提取到 {len(answers)} 個答案：{" ".join(answers)}')
        
        key = f'{roc_year}_{subject}'
        results[key] = {
            'roc_year': roc_year,
            'subject': subject,
            'answers': answers,  # 索引 0 = Q1, 1 = Q2, ...
        }
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f'\n已儲存：{OUTPUT_FILE}')
    total = sum(len(v['answers']) for v in results.values())
    print(f'總答案數：{total}')


if __name__ == '__main__':
    run()
