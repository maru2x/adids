import time


from model_factory import *
from settings_loader import *
from session_controller import *

def main():

    # 設定読み込み
    loader = SettingsLoader()

    # セッションの初期化
    session = SessionController(loader)

    # モデルの初期化
    model_factory = ModelFactory(
        model_code=loader.get('MODEL_CODE'),
        user_dir_path=f"{loader.get('USER_DIR')}",
        foundation_model_path=f"{loader.get('FOUNDATION_MODEL_PATH')}",
        input_dim=loader.resolve_input_dim()
    )

    # セッションの開始
    session.run(model_factory)

if __name__ == "__main__":
    main()
