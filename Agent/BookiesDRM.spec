# 포함할 데이터 (이미지 파일 등)
datas = [
    ("img/sk_shieldus_butterfly_rgb_kr.png", "img"),
    ("img/EQST.png", "img"),
    ("img/sk_shieldus_butterfly_rgb_kr_ico.ico", "img"),
    ("img/back.png", "img"),
    ("img/next.png", "img"),
    ("img/plus.png", "img"),
    ("img/minus.png", "img"),
    ("img/page_1.png", "img"),
    ("img/page_2.png", "img")
]

# 불필요한 모듈 제외
excluded_modules = [
]

# PyInstaller 분석 단계
block_cipher = None

a = Analysis([
    "agent_fffffff.py"],
    pathex=[os.getcwd()],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=excluded_modules,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher
)

# PyInstaller 패키징 단계
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="agent_fffffff",
    debug=False,
    strip=False,
    upx=True,
    console=False,  # GUI 모드
    icon="img/sk_shieldus_butterfly_rgb_kr_ico.ico"  # EXE 아이콘 지정
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name="agent_fffffff"
)
