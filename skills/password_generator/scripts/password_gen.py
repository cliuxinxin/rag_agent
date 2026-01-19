import sys
import random
import string

def generate_password(length):
    """
    生成包含大小写字母、数字和符号的密码
    """
    # 定义字符集
    uppercase = string.ascii_uppercase  # A-Z
    lowercase = string.ascii_lowercase  # a-z
    digits = string.digits              # 0-9
    symbols = '!@#$%^&*()_+-=[]{}|;:,.<>?'  # 符号
    
    # 确保每种类型至少有一个字符
    password_chars = [
        random.choice(uppercase),
        random.choice(lowercase),
        random.choice(digits),
        random.choice(symbols)
    ]
    
    # 组合所有字符集
    all_chars = uppercase + lowercase + digits + symbols
    
    # 填充剩余长度
    remaining_length = length - 4
    if remaining_length > 0:
        password_chars.extend(random.choice(all_chars) for _ in range(remaining_length))
    
    # 随机打乱字符顺序
    random.shuffle(password_chars)
    
    # 组合成字符串
    return ''.join(password_chars)

def main():
    try:
        # 检查参数数量
        if len(sys.argv) < 2:
            print('错误：请提供密码长度参数')
            print('用法：password_generator <长度>')
            print('示例：password_generator 12')
            sys.exit(1)
        
        # 获取长度参数
        try:
            length = int(sys.argv[1])
        except ValueError:
            print(f'错误：长度参数必须是数字，收到：{sys.argv[1]}')
            sys.exit(1)
        
        # 验证长度范围
        if length < 8:
            print('警告：密码长度小于8位，安全性较低')
            print('建议使用至少12位长度的密码')
            # 继续生成，但给出警告
        elif length > 50:
            print('警告：密码长度超过50位，可能不被所有系统支持')
            # 继续生成，但给出警告
        
        # 生成密码
        password = generate_password(length)
        
        # 输出结果
        print(f'生成的密码（{length}位）：')
        print(password)
        
        # 额外信息
        print('\n密码强度分析：')
        print(f'- 长度：{len(password)} 位')
        
        # 统计字符类型
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_symbol = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password)
        
        print(f'- 包含大写字母：{"是" if has_upper else "否"}')
        print(f'- 包含小写字母：{"是" if has_lower else "否"}')
        print(f'- 包含数字：{"是" if has_digit else "否"}')
        print(f'- 包含符号：{"是" if has_symbol else "否"}')
        
        # 强度评估
        if length >= 16 and has_upper and has_lower and has_digit and has_symbol:
            print('- 强度评估：非常强')
        elif length >= 12 and has_upper and has_lower and has_digit and has_symbol:
            print('- 强度评估：强')
        elif length >= 8 and (has_upper or has_lower) and has_digit:
            print('- 强度评估：中等')
        else:
            print('- 强度评估：弱')
        
    except Exception as e:
        print(f'生成密码时发生错误：{str(e)}')
        sys.exit(1)

if __name__ == '__main__':
    main()
