import psutil
import json

def get_status():
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    data = {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_used_gb": round(mem.used / (1024**3), 2),
        "memory_total_gb": round(mem.total / (1024**3), 2),
        "memory_percent": mem.percent,
        "disk_percent": disk.percent
    }
    print(json.dumps(data, indent=2))

if __name__ == "__main__":
    get_status()
