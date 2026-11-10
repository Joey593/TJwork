import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')
DATA = Path(os.getenv('DATA_DIR', str(ROOT / 'data'))).resolve()
DATA.mkdir(parents=True, exist_ok=True)
ARTIFACTS = DATA / 'artifacts'
ARTIFACTS.mkdir(exist_ok=True)
DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{DATA / "platform.db"}')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'Admin12345!')
JWT_SECRET = os.getenv('JWT_SECRET')
if not JWT_SECRET:
    import secrets
    secret_file = DATA / '.jwt-secret'
    if not secret_file.exists():
        secret_file.write_text(secrets.token_urlsafe(48))
        secret_file.chmod(0o600)
    JWT_SECRET = secret_file.read_text().strip()
