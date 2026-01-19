import sys
import json
import matplotlib.pyplot as plt
import datetime
import platform

# --- 核心修改：配置中文字体 ---
def set_chinese_font():
    system_name = platform.system()
    if system_name == "Windows":
        # Windows 默认黑体
        plt.rcParams['font.sans-serif'] = ['SimHei']
    elif system_name == "Darwin":
        # Mac OS 默认字体
        plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'PingFang SC', 'Heiti TC']
    else:
        # Linux / Docker 容器
        plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'DejaVu Sans']
    
    # 解决负号显示为方块的问题
    plt.rcParams['axes.unicode_minus'] = False

def plot_chart(json_str):
    try:
        # 1. 设置字体
        set_chinese_font()
        
        data = json.loads(json_str)
        
        chart_type = data.get("type", "line")
        labels = data.get("labels", [])
        values = data.get("values", [])
        title = data.get("title", "Chart")
        
        plt.figure(figsize=(10, 6))
        
        if chart_type == "bar":
            # 柱状图颜色优化
            plt.bar(labels, values, color='#4e79a7', alpha=0.8)
        else:
            plt.plot(labels, values, marker='o', linestyle='-', color='#e15759', linewidth=2)
            
        plt.title(title, fontsize=16, pad=20)
        plt.xlabel("类别 (Category)", fontsize=12)
        plt.ylabel("数值 (Values)", fontsize=12)
        plt.grid(True, alpha=0.3, linestyle='--')
        
        # 自动调整布局，防止字被切掉
        plt.tight_layout()
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"chart_{timestamp}.png"
        
        plt.savefig(filename, dpi=100)
        plt.close()
        
        print(f"Success! Chart saved to: {filename}")
        
    except Exception as e:
        print(f"Error creating chart: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        full_json = " ".join(sys.argv[1:])
        plot_chart(full_json)
    else:
        print("Error: No data provided.")