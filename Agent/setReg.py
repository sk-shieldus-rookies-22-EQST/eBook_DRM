import winreg as reg
import sys
import ctypes
import os

# Custom URI 스키마 이름과 실행할 프로그램 경로 설정
custom_scheme_name = "BookiesDRM"  # 예: BookiesDRM:// 이름에 _ 사용 시 실행 불가
executable_path = r"C:\BookiesDRM\BookiesDRM.exe"  # 실행할 프로그램 경로

def register_custom_uri_scheme(scheme_name, exe_path):
    try:
        # Custom URI 스키마의 레지스트리 경로
        key_path = f"SOFTWARE\\Classes\\{scheme_name}"
        
        # 1. URI 스키마의 기본 키 생성
        with reg.CreateKey(reg.HKEY_CURRENT_USER, key_path) as key:
            reg.SetValueEx(key, None, 0, reg.REG_SZ, f"URL:{scheme_name} Protocol")
            reg.SetValueEx(key, "URL Protocol", 0, reg.REG_SZ, "")

        # 2. shell\opens\command 키 생성
        command_key_path = f"{key_path}\\shell\\open\\command"
        with reg.CreateKey(reg.HKEY_CURRENT_USER, command_key_path) as command_key:
            reg.SetValueEx(command_key, None, 0, reg.REG_SZ, f'"{exe_path}" "%1"')

        print(f"Custom URI scheme '{scheme_name}://' successfully registered!")
    except Exception as e:
        print(f"Error registering custom URI scheme: {e}")

def is_admin():
    """관리자 권한 여부 확인"""
    try:
        return os.getuid() == 0
    except AttributeError:
        # Windows에서는 os.getuid()가 없기 때문에 ctypes를 사용하여 관리자 권한 여부를 확인
        return ctypes.windll.shell32.IsUserAnAdmin() != 0

def run_as_admin():
    """관리자 권한으로 스크립트를 재실행"""
    if is_admin():
        register_custom_uri_scheme(custom_scheme_name, executable_path)
    else:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, ' '.join([sys.argv[0]] + sys.argv[1:]), None, 1)
        

if __name__ == "__main__":
    run_as_admin()
