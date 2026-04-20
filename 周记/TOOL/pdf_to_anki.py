"""
PDF讲义（填空题 + 连线题） → Anki卡片集合 (.apkg) 转换脚本

使用方法：
  python pdf_to_anki.py <pdf_file_path> <output_apkg_name>
  
例子：
  python pdf_to_anki.py "生理学·绪论复习题.pdf" "生理学复习"
"""

import json
import os
import re
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from typing import List, Dict, Tuple
import shutil

# 尝试导入pdfplumber，如果没有就提示用户安装
try:
    import pdfplumber
except ImportError:
    print("❌ 需要安装 pdfplumber 库")
    print("请运行: pip install pdfplumber")
    exit(1)


class PDFToAnkiConverter:
    """PDF讲义转Anki卡片的转换器"""
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.fill_blank_questions = []  # 填空题：[(题号, 题目, 答案), ...]
        self.line_matching_questions = []  # 连线题：[(题号, 左侧, 右侧, 答案), ...]
        
    def extract_text_from_pdf(self) -> str:
        """从PDF提取全部文本"""
        text = ""
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for page in pdf.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + "\n"
            if not text.strip():
                print("⚠️ PDF为空或无法提取文本，尝试使用备选方案...")
                return ""
            return text
        except Exception as e:
            print(f"⚠️ 读取PDF时出现错误: {e}")
            return ""
    
    def parse_fill_blank_questions(self, text: str):
        """
        解析填空题部分
        格式示例：
        体液可分为细胞内液和细胞外液，其中细胞内液约占体液总量的______，占体重的______%；
        
        答案部分格式：
        2/3；40；1/3；20
        """
        # 找到"挖空题"和"参考答案"之间的内容
        fill_blank_section = re.search(
            r'一、?挖空题.*?(?=参考答案|连线题|$)',
            text,
            re.DOTALL
        )
        
        if not fill_blank_section:
            print("⚠️ 未找到挖空题部分")
            return
        
        fill_text = fill_blank_section.group(0)
        
        # 提取各个小节（体液与内环境、机体调节方式等）
        sections = re.split(r'【.*?】', fill_text)
        
        question_id = 1
        for section in sections[1:]:  # 跳过第一个空段
            # 按句子拆分题目
            sentences = re.split(r'(?<=[。；，])\s*', section)
            
            for sentence in sentences:
                sentence = sentence.strip()
                if '______' in sentence:
                    # 计算这个句子有多少个空
                    blanks_count = sentence.count('______')
                    
                    # 问题形式：题号 + 题目
                    question_text = f"第{question_id}题：{sentence}"
                    
                    # 暂时设置占位符答案（后续会从参考答案匹配）
                    self.fill_blank_questions.append({
                        'id': question_id,
                        'question': question_text,
                        'blanks': blanks_count,
                        'answer': '(待填充答案)'  # 临时
                    })
                    question_id += 1
    
    def parse_answers(self, text: str):
        """解析参考答案部分"""
        # 找到参考答案区域
        answer_section = re.search(
            r'参考答案.*?挖空题答案(.*?)(?=连线题答案|$)',
            text,
            re.DOTALL
        )
        
        if not answer_section:
            print("⚠️ 未找到参考答案部分")
            return {}
        
        answers_text = answer_section.group(1)
        
        # 答案格式：直接一行一行列出，用；分隔多个空的答案
        # 例如：2/3；40；1/3；20
        answer_lines = [line.strip() for line in answers_text.split('\n') if line.strip()]
        
        # 展平所有答案（因为多个空可能在一行用；分隔）
        all_answers = []
        for line in answer_lines:
            # 使用；或，来分隔
            parts = re.split(r'[；，]', line)
            all_answers.extend([p.strip() for p in parts if p.strip()])
        
        return all_answers
    
    def match_answers_to_questions(self, all_answers: List[str]):
        """把答案匹配到对应的填空题"""
        answer_idx = 0
        
        for q in self.fill_blank_questions:
            blanks = q['blanks']
            
            # 把连续的 blanks 个答案合并成一个，用 / 分隔
            if answer_idx + blanks <= len(all_answers):
                answers = all_answers[answer_idx:answer_idx + blanks]
                q['answer'] = ' / '.join(answers)
                answer_idx += blanks
    
    def parse_line_matching(self, text: str):
        """
        解析连线题部分
        格式示例：
        连线题： 左侧（调节方式） 右侧（特点/描述）
        1. 神经调节 A. 缓慢、持久、不够精确
        2. 体液调节 B. 快速、短暂、精确
        ...
        
        答案格式：
        连线题 1 1-B；2-A；3-C；4-D
        """
        # 找到"连线题："的所有段落
        line_sections = re.finditer(
            r'连线题：\s*左侧(.*?)(?=连线题：|挖空题答案|$)',
            text,
            re.DOTALL
        )
        
        matching_id = 1
        for section in line_sections:
            section_text = section.group(1)
            
            # 提取左侧选项
            left_options = {}
            for match in re.finditer(r'(\d+)\.\s*([^\n]+)', section_text):
                left_options[match.group(1)] = match.group(2).strip()
            
            # 提取右侧选项
            right_options = {}
            for match in re.finditer(r'([A-Z]+)\.\s*([^\n]+)', section_text):
                right_options[match.group(1)] = match.group(2).strip()
            
            # 构造连线题（每一个左侧选项作为一个卡片正面，右侧选项作为反面）
            for left_id, left_text in left_options.items():
                self.line_matching_questions.append({
                    'id': f"连线{matching_id}-{left_id}",
                    'question': f"连线题 {matching_id}：{left_text}",
                    'left_id': left_id,
                    'matching_id': matching_id,
                    'answer': '(待填充答案)'  # 临时
                })
            
            matching_id += 1
    
    def parse_line_matching_answers(self, text: str):
        """解析连线题答案"""
        # 答案格式：连线题 1 1-B；2-A；3-C；4-D
        line_answers = re.findall(
            r'连线题\s*(\d+)\s+([\d\-A-Z；]+)',
            text
        )
        
        answer_dict = {}
        for matching_id, answer_str in line_answers:
            # 解析答案字符串
            pairs = re.findall(r'(\d+)-([A-Z]+)', answer_str)
            answer_dict[int(matching_id)] = {int(left): right for left, right in pairs}
        
        # 匹配答案到连线题
        for q in self.line_matching_questions:
            m_id = q['matching_id']
            left_id = int(q['left_id'])
            
            if m_id in answer_dict and left_id in answer_dict[m_id]:
                q['answer'] = answer_dict[m_id][left_id]
    
    def parse(self):
        """执行完整的解析"""
        print("📖 正在读取PDF文件...")
        text = self.extract_text_from_pdf()
        
        print("🔍 正在解析填空题...")
        self.parse_fill_blank_questions(text)
        all_answers = self.parse_answers(text)
        self.match_answers_to_questions(all_answers)
        
        print("🔗 正在解析连线题...")
        self.parse_line_matching(text)
        self.parse_line_matching_answers(text)
        
        print(f"✅ 解析完成！")
        print(f"   - 填空题: {len(self.fill_blank_questions)} 题")
        print(f"   - 连线题: {len(self.line_matching_questions)} 题")
    
    def generate_apkg(self, output_name: str):
        """生成.apkg文件"""
        print(f"📦 正在生成 {output_name}.apkg...")
        
        # 创建临时目录用于存放anki文件
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. 创建数据库文件 (SQLite)
            db_path = os.path.join(tmpdir, 'collection.anki2')
            self._create_anki_database(db_path)
            
            # 2. 创建media文件夹（即使为空）
            media_dir = os.path.join(tmpdir, 'media')
            os.makedirs(media_dir, exist_ok=True)
            
            # 3. 创建空的media JSON文件
            media_json_path = os.path.join(tmpdir, 'media')
            with open(media_json_path, 'w', encoding='utf-8') as f:
                json.dump({}, f)
            
            # 4. 将临时文件打包成.apkg（本质是ZIP）
            output_path = f"{output_name}.apkg"
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as apkg:
                apkg.write(db_path, arcname='collection.anki2')
                apkg.write(media_json_path, arcname='media')
            
            print(f"✅ 成功生成: {output_path}")
            return output_path
    
    def _create_anki_database(self, db_path: str):
        """创建Anki的SQLite数据库并插入卡片"""
        # 这是一个简化的Anki数据库创建逻辑
        # 完整的Anki数据库结构会更复杂，但对于基础功能足够了
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 创建基本表（简化版）
        # 注意：真正的Anki数据库还有更多表和字段，这里只是创建最小化版本
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS col (
                id INTEGER PRIMARY KEY,
                crt INTEGER,
                mod INTEGER,
                scm INTEGER,
                ver INTEGER,
                dty INTEGER,
                usn INTEGER,
                ls INTEGER,
                conf TEXT,
                models TEXT,
                decks TEXT,
                dconf TEXT,
                tags TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY,
                guid TEXT UNIQUE,
                mid INTEGER,
                mod INTEGER,
                usn INTEGER,
                tags TEXT,
                flds TEXT,
                sfld TEXT,
                csum INTEGER,
                flags INTEGER,
                data TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY,
                nid INTEGER,
                did INTEGER,
                ord INTEGER,
                mod INTEGER,
                usn INTEGER,
                type INTEGER,
                queue INTEGER,
                due INTEGER,
                ivl INTEGER,
                factor INTEGER,
                reps INTEGER,
                lapses INTEGER,
                left INTEGER,
                odue INTEGER,
                odid INTEGER,
                did_original INTEGER,
                flags INTEGER,
                data TEXT
            )
        ''')
        
        # 插入collection记录
        import time
        now = int(time.time() * 1000)
        
        cursor.execute('''
            INSERT INTO col VALUES (1, ?, ?, ?, 11, 0, -1, 0, ?, ?, ?, ?, ?)
        ''', (now, now, now, '{}', '{}', '{}', '{}', '{}'))
        
        # 插入笔记和卡片
        nid_base = 1000000000
        cid_base = 1000000000
        
        # 处理填空题
        for i, q in enumerate(self.fill_blank_questions):
            nid = nid_base + i
            cid = cid_base + i
            
            guid = f"anki-fill-{i}"
            fields = f"{q['question']}\t{q['answer']}"
            
            cursor.execute('''
                INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data)
                VALUES (?, ?, 1, ?, -1, '', ?, ?, 0, 0, '')
            ''', (nid, guid, now, fields, q['question']))
            
            cursor.execute('''
                INSERT INTO cards (id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, did_original, flags, data)
                VALUES (?, ?, 1, 0, ?, -1, 0, 0, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, '')
            ''', (cid, nid, now, now // 86400))
        
        # 处理连线题
        offset = len(self.fill_blank_questions)
        for i, q in enumerate(self.line_matching_questions):
            nid = nid_base + offset + i
            cid = cid_base + offset + i
            
            guid = f"anki-line-{i}"
            fields = f"{q['question']}\t{q['answer']}"
            
            cursor.execute('''
                INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data)
                VALUES (?, ?, 1, ?, -1, '', ?, ?, 0, 0, '')
            ''', (nid, guid, now, fields, q['question']))
            
            cursor.execute('''
                INSERT INTO cards (id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, did_original, flags, data)
                VALUES (?, ?, 1, 0, ?, -1, 0, 0, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, '')
            ''', (cid, nid, now, (now + 86400000) // 86400))
        
        conn.commit()
        conn.close()


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("❌ 使用方法: python pdf_to_anki.py <pdf_file> [output_name]")
        print("\n例子:")
        print("  python pdf_to_anki.py '生理学·绪论复习题.pdf' '生理学复习'")
        sys.exit(1)
    
    pdf_file = sys.argv[1]
    output_name = sys.argv[2] if len(sys.argv) > 2 else "output"
    
    if not os.path.exists(pdf_file):
        print(f"❌ 文件不存在: {pdf_file}")
        sys.exit(1)
    
    # 执行转换
    converter = PDFToAnkiConverter(pdf_file)
    converter.parse()
    converter.generate_apkg(output_name)
    
    print("\n✨ 转换完成！你可以在Anki中导入生成的.apkg文件。")


if __name__ == '__main__':
    main()
