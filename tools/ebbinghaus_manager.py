import sys
import json
from datetime import datetime, date
from pathlib import Path

# 数据文件存放在工作区根目录下
PLAN_FILE = Path(r'd:/postgraduate_exam/postgraduate_admission_exam_journey/ebbinghaus_plan.json')

# 艾宾浩斯经典遗忘曲线间隔（按天算）
# 0天(当晚)，1天，2天，4天，7天，15天，30天
BASE_INTERVALS = {
    0: "👀 当晚复习 (大约睡前过一遍，重中之重)",
    1: "🗓️ 第1天复习 (昨日学过的内容)",
    2: "🗓️ 第2天复习",
    4: "🗓️ 第4天复习",
    7: "🗓️ 第7天复习 (一周巩固)",
    15: "🗓️ 第15天复习 (半个月)",
    30: "🗓️ 第30天复习 (一个月强化)"
}

ROLLING_DAYS = 30 # 30天以后，每隔30天就会再次滚动提醒一遍

def get_interval_name(days):
    if days in BASE_INTERVALS:
        return BASE_INTERVALS[days]
    return f"🔄 滚动复习 (距初学第 {days} 天)"

def get_milestones_up_to(diff):
    """根据当前差值天数，计算出从0天到现在所有的复习节点（包含无限滚动）"""
    milestones = list(BASE_INTERVALS.keys())
    last_base = max(milestones)
    if diff > last_base:
        k = 1
        while last_base + k * ROLLING_DAYS <= diff:
            milestones.append(last_base + k * ROLLING_DAYS)
            k += 1
    return sorted(milestones)

def load_data():
    if PLAN_FILE.exists():
        with open(PLAN_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"records": []}

def save_data(data):
    PLAN_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PLAN_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def add_record(name):
    data = load_data()
    today_str = date.today().isoformat()
    data["records"].append({"name": name, "date": today_str, "completed": []})
    save_data(data)
    print(f"\n✅ 成功添加新学习内容: {name}")
    print(f"👉 添加日期: {today_str}\n")
    print(f"提示: 今晚睡前记得快速浏览一遍这份PDF哦！\n")

def mark_done(keyword):
    data = load_data()
    today = date.today()
    found = False
    
    for record in data["records"]:
        if keyword.lower() in record["name"].lower():
            found = True
            try:
                record_date = datetime.strptime(record["date"], "%Y-%m-%d").date()
                diff = (today - record_date).days
                
                # 凡是小于等于今天天数的节点（含滚动），只要该复习的，都标为已完成
                done_list = record.get("completed", [])
                milestones = get_milestones_up_to(diff)
                for iv in milestones:
                    if iv not in done_list:
                        done_list.append(iv)
                record["completed"] = done_list
                print(f"✅ 打卡成功: {record['name']} (所有积压任务已清空)")
            except Exception:
                continue
            
    if found:
        save_data(data)
    else:
        print(f"❌ 未找到包含关键词 [{keyword}] 的文章任务")

def show_today():
    data = load_data()
    today = date.today()
    
    print(f"\n📅 今天是: {today.isoformat()}")
    print("=" * 50)
    print("🎯 今天你需要回顾的批注版 PDF/文章（包含遗漏顺延与无限滚动）：\n")
    
    has_task = False
    tasks = {}
    
    for record in data["records"]:
        try:
            record_date = datetime.strptime(record["date"], "%Y-%m-%d").date()
            diff = (today - record_date).days
            if diff < 0: continue
            
            completed = record.get("completed", [])
            milestones = get_milestones_up_to(diff)
            
            # 找出所有应该复习但尚未打卡的节点
            pending = [iv for iv in milestones if iv not in completed]
            
            if pending:
                # 我们只把它放在最古老的一个未完成的节点上提示，以免在一个单子里出现多次
                target_interval = pending[0]
                label = record["name"]
                if diff > target_interval:
                    label += f"  ⚠️ (漏打卡顺延, 距初学已过{diff}天)"
                    
                if target_interval not in tasks:
                    tasks[target_interval] = []
                tasks[target_interval].append(label)
        except Exception:
            continue
    
    for diff in sorted(tasks.keys()):
        names = tasks[diff]
        if names:
            has_task = True
            print(f"【{get_interval_name(diff)}】:")
            for name in names:
                print(f"   - {name}")
            print("")
    
    if not has_task:
        print("🎉 今天目前没有需要复习的历史内容，专心突击新文章吧！\n")
    print("=" * 50)
    print("💡 提示: 复习完后别忘了用 python tools/ebbinghaus_manager.py done \"文章关键词\" 进行打卡哦！\n")

def interactive_mode():
    while True:
        print("\n" + "="*45)
        print(" 🧠 复习进度管理 🧠")
        print("="*45)
        print("  1. 📅 查看今天复习任务")
        print("  2. ➕ 录入新看完的文章")
        print("  3. ✅ 打卡已复习的文章")
        print("  0. ❌ 退出退出程序")
        print("="*45)
        choice = input("👉 请输入数字选择操作 (0-3): ").strip()
        
        if choice == '1':
            show_today()
        elif choice == '2':
            name = input("\n📝 请输入新的文章名称: ").strip()
            if name:
                add_record(name)
            else:
                print("❌ 取消录入，名称不能为空。")
        elif choice == '3':
            keyword = input("\n✅ 请输入要打卡的文章名称(输入片段即可): ").strip()
            if keyword:
                mark_done(keyword)
            else:
                print("❌ 取消打卡，名称不能为空。")
        elif choice == '0':
            print("\n👋 祝考研/六级顺利，再见！\n")
            break
        else:
            print("\n❌ 选项无效，请重新输入！")

if __name__ == "__main__":
    if len(sys.argv) == 1:
        # 如果没有任何参数，直接进入无脑交互模式
        try:
            interactive_mode()
        except KeyboardInterrupt:
            print("\n👋 强制退出，再见！")
        sys.exit(0)
        
    action = sys.argv[1]
    if action == "add":
        if len(sys.argv) < 3:
            print("❌ 错误: 请提供文章名称！\n例如: python tools/ebbinghaus_manager.py add \"2025.06阅读Passage2\"")
        else:
            add_record(sys.argv[2])
    elif action == "today":
        show_today()
    elif action == "done":
        if len(sys.argv) < 3:
            print("❌ 错误: 请提供用来打卡的文章名称（一个关键词片段即可）！")
        else:
            mark_done(sys.argv[2])
    else:
        print("❌ 未知命令。支持的命令: add, today, done")
