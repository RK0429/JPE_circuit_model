# JPE_circuit_model

Josephson Plasma Emitter の LTSpice 回路モデル

## 概要

JPE_circuit_model は、Josephson Plasma Emitter の動作を LTSpice でシミュレートするための回路モデルおよび解析ツール群を提供します。LTSpice 用のモデルファイルと、シミュレーション結果を読み込み、処理・可視化する Python スクリプトを備えており、実験データのフィッティング解析もサポートします。

## 目次

- [JPE\_circuit\_model](#jpe_circuit_model)
  - [概要](#概要)
  - [目次](#目次)
  - [導入方法](#導入方法)
    - [環境構築](#環境構築)
      - [動作環境](#動作環境)
      - [Python のインストール](#python-のインストール)
      - [依存ライブラリのインストール](#依存ライブラリのインストール)
    - [モデルのダウンロード](#モデルのダウンロード)
  - [使用方法](#使用方法)
    - [LTSpice でのシミュレーション](#ltspice-でのシミュレーション)
    - [Python スクリプトによる解析](#python-スクリプトによる解析)
      - [時間平均解析](#時間平均解析)
      - [位相解析](#位相解析)
      - [R\_int フィッティング解析](#r_int-フィッティング解析)
      - [アンテナパラメータフィッティング解析 (with\_L)](#アンテナパラメータフィッティング解析-with_l)
  - [例](#例)
  - [貢献](#貢献)
  - [ライセンス](#ライセンス)

## 導入方法

### 環境構築

#### 動作環境

- Windows 10 以降
- LTSpice 24.x.x
- Python 3.10 以上

#### Python のインストール

1. Python を公式サイト (<https://www.python.org/>) からダウンロード・インストールしてください。
2. 仮想環境を作成します:

   ```bash
   python -m venv .venv
   ```

3. 仮想環境を有効化します（PowerShell の場合）:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

#### 依存ライブラリのインストール

Poetry を使用する場合:

```bash
pip install poetry
poetry install
```

pip を直接使用する場合:

```bash
pip install -r requirements.txt
```

### モデルのダウンロード

```bash
git clone https://github.com/RK0429/JPE_circuit_model.git
cd JPE_circuit_model
```

## 使用方法

### LTSpice でのシミュレーション

1. `examples` フォルダにある `.asc` ファイル（例: `JPE_3stacks.asc`）を LTSpice で開きます。
2. `.tran 0 2 0 10u` が設定済みですので、そのままシミュレーションを実行してください。
3. "V(nt)", "V(na)", "I(Rad)", "I(Rgnd)" のデータをtxt形式でエクスポートします。

### Python スクリプトによる解析

#### 時間平均解析

1. 出力したtxtファイルを可視化します。

```bash
python post_processing/time_averaging.py \
  data/dc_sweep_JPE.txt \
  --output_file results/dc_sweep_processed.txt \
  --plot_path results/dc_sweep_plot.png \
  --vt_plot_path results/voltage_time_plot.png
```

#### 位相解析

```bash
python post_processing/phase_analysis.py \
  data/dc_sweep_JPE_phase_original.txt \
  results/dc_sweep_JPE_phase_processed.txt \
  --plot-file results/dc_sweep_phase_plot.pdf
```

#### R_int フィッティング解析

```bash
python fitting/R_int/main.py \
  data/R_int_data.txt \
  --output-data results/R_int_processed.dat \
  --output-plot results/R_int_plots.pdf
```

#### アンテナパラメータフィッティング解析 (with_L)

```bash
python fitting/antenna_params/with_L/main.py \
  --bo-file data/bolometer_output.csv \
  --ive-file data/ive_data.csv \
  --txt-file data/dc_sweep_JPE.txt \
  --fig6 results/Fig6.pdf \
  --fig10 results/Fig10.pdf
```

## 例

- `examples/JPE_3stacks.asc`: 3段積層モデルの回路図
- `examples/JPE_3stacks_RC.asc`: 抵抗・容量モデルの回路図

## 貢献

プルリクエストや Issue の投稿は歓迎します。コーディング規約やテストの追加などにご協力ください。

## ライセンス

MIT ライセンスのもとで公開されています。詳細は [LICENSE](LICENSE) をご覧ください。
