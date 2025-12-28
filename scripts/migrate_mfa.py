import sys
import os
from sqlalchemy import text

# Add master to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from master.db.session import engine

def migrate_mfa():
    print("Migrating Database for MFA...")
    with engine.connect() as conn:
        # Add mfa_enabled
        try:
            conn.execute(text('ALTER TABLE users ADD COLUMN mfa_enabled BOOLEAN DEFAULT 0'))
            conn.commit()
            print('  Added mfa_enabled')
        except Exception as e:
            print(f'  mfa_enabled might exist: {e}')

        # Add mfa_channel_id
        try:
            conn.execute(text('ALTER TABLE users ADD COLUMN mfa_channel_id INTEGER REFERENCES communication_channels(id)'))
            conn.commit()
            print('  Added mfa_channel_id')
        except Exception as e:
            print(f'  mfa_channel_id might exist: {e}')

        # Add login_otp
        try:
            conn.execute(text('ALTER TABLE users ADD COLUMN login_otp VARCHAR'))
            conn.commit()
            print('  Added login_otp')
        except Exception as e:
            print(f'  login_otp might exist: {e}')

        # Add login_otp_expires
        try:
            conn.execute(text('ALTER TABLE users ADD COLUMN login_otp_expires DATETIME'))
            conn.commit()
            print('  Added login_otp_expires')
        except Exception as e:
            print(f'  login_otp_expires might exist: {e}')
            
    print("Migration complete.")

if __name__ == "__main__":
    migrate_mfa()
