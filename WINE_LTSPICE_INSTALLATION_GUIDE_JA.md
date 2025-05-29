# Mac用 Wineベース LTspice インストールガイド

このガイドは、MacネイティブのLTspiceを使用する際に`.raw`ファイルや`.log`ファイルが生成されない問題を解決するため、macOS上でWineベースのLTspiceを正常にインストールし設定する手順を文書化したものです。

## 前提条件

- macOS (Apple Silicon M4 Proでテスト済み)
- Homebrew パッケージマネージャー
- インストール時の管理者権限

## インストール手順

### 1. Homebrewのインストール (未インストールの場合)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 2. Homebrewを使用してWineをインストール

```bash
brew install --cask wine-stable
```

**注**: `wine-stable` はIntel macOS向けにビルドされており、Rosetta 2が必要です。プロンプトが表示されたら、以下のコマンドでRosetta 2をインストールしてください。

```bash
softwareupdate --install-rosetta --agree-to-license
```

### 3. Windows版 LTspice インストーラーのダウンロード

```bash
cd ~/Downloads
curl -L -o LTspice64.exe "https://ltspice.analog.com/software/LTspice64.exe"
```

### 4. Wineを使用してLTspiceをインストール

```bash
wine ~/Downloads/LTspice64.exe
```

Windowsインストーラーウィザードに従ってください。デフォルトのインストールパスは以下の通りです。
`C:\Program Files\LTC\LTspiceXVII\` (Wineの仮想C:ドライブ内)

### 5. 環境変数の設定

シェル設定ファイル (`~/.zshrc` または `~/.bashrc`) に以下を追加します。

```bash
# LTspice Wine 設定
export LTSPICEFOLDER="$HOME/.wine/drive_c/Program Files/LTC/LTspiceXVII"
export LTSPICEEXECUTABLE="XVIIx64.exe"
```

その後、シェル設定を再読み込みします。

```bash
source ~/.zshrc  # または source ~/.bashrc
```

### 6. インストールの確認

Wine経由でLTspiceが起動できることをテストします。

```bash
wine "$LTSPICEFOLDER/$LTSPICEEXECUTABLE" -h
```

## PythonスクリプトでWineベースのLTspiceを使用する

### セットアップのテスト

1. プロジェクトディレクトリに移動します。

    ```bash
    cd /path/to/your/project
    ```

2. シミュレーションを実行します。

    ```bash
    ./run_edit_simple_resonant.sh ./examples/simple_resonant.asc \
      -o ./examples/simple_resonant_modified.asc \
      --output-folder ./simulation/simple_resonant \
      -p "R1=20n"
    ```

### 期待される出力

成功すると、以下が表示されます。

- 成功を示すシミュレーションメッセージ
- 出力フォルダに生成されたファイル:
  - `.asc` - 変更された回路ファイル
  - `.net` - ネットリストファイル
  - `.raw` - シミュレーション結果 (波形データ)
  - `.log` - シミュレーションログファイル

### Wine版とネイティブ版LTspiceの確認

どちらのバージョンのLTspiceが使用されているかを確認するには：

```python
from cespy.simulators.ltspice_simulator import LTspice
print("Using Mac native LTspice:", LTspice.using_macos_native_sim())
# False と表示されるはずです (WineベースのLTspiceを示します)
```

## トラブルシューティング

### 一般的な問題

1. **バッチモードではなくWine GUIが開く**: 一部の操作ではこれが正常な動作です。シミュレーションはそれでも正常に完了するはずです。

2. **パーミッションエラー**: 出力ディレクトリが書き込み可能であることを確認してください。

    ```bash
    chmod -R 755 /path/to/output/directory
    ```

3. **パスが見つからないエラー**: WineプレフィックスとLTspiceのインストールを確認してください。

    ```bash
    ls "$HOME/.wine/drive_c/Program Files/LTC/LTspiceXVII/"
    ```

4. **環境変数が読み込まれない**: エクスポートを追加した後、シェル設定ファイルを `source` したことを確認してください。

### Wine特有のメッセージ

実行中に様々なWineメッセージ (MoltenVK情報、fixme警告など) が表示されることがあります。これらは正常であり、シミュレーションが正常に完了する限り無視できます。

## WineベースLTspiceの利点

1. **完全なコマンドラインサポート**: `.asc`ファイルからネットリストを生成可能
2. **バッチモード操作**: `-Run` および `-netlist` フラグをサポート
3. **完全なファイル生成**: 期待されるすべての出力ファイル (`.raw`, `.log`, `.net`) を生成
4. **Python連携**: `cespy` および `PyLTSpice` ライブラリとシームレスに動作

## パフォーマンスに関する考慮事項

- Wineはネイティブアプリケーションと比較して多少のオーバーヘッドを追加します
- Wineの初期化のため、最初の実行は遅くなる場合があります
- その後の実行は通常高速です
- GUI操作には多少の遅延が見られる場合があります

## 代替ソリューション

WineベースのLTspiceがニーズに合わない場合は、以下を検討してください。

1. **NGspice**: ネイティブMacサポートを備えたオープンソースシミュレータ
2. **Xyce**: サンディア国立研究所の並列回路シミュレータ
3. **QUCS**: Qtベースの回路シミュレータ
4. **Windows VMまたはリモートマシンでのシミュレーション実行**

## 結論

WineベースのLTspiceは、MacネイティブLTspiceの制限を正常に解決し、macOS上での回路シミュレーションワークフローにおける完全なコマンドライン自動化と適切なファイル生成を可能にします。
