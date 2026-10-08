# AI生成 Treewidth Solver Benchmark Suite

> **注意**: 本リポジトリのコード、ドキュメント、設定ファイルを含むすべての内容は、AI (Claude) によって生成されたものです。人間が手作業で記述した部分はありません。

[English](README.md)

複数の公開されている treewidth ソルバーを統一的なインターフェースでベンチマーク比較するためのツールキットです。

## 前提条件

必須:
- Python 3.8+
- Git

ソルバーごとの依存:
- **Java ソルバー** (twalgor-tw, twalgor-rtw, tamaki-2017, jdrasil): JDK 8+
- **C/C++ ソルバー** (tamaki-2016, tdlib-p17, flowcutter-17, htd, minfill-mrs, minfillbg-mrs): GCC 7+（C++17 対応の g++）と `make`
  - **tdlib-p17** は C++17（ビルド時にインライン変数を挿入します）、Boost、autotools、libtool が必要です（Debian/Ubuntu: `sudo apt install libboost-graph-dev libboost-thread-dev autoconf automake libtool`）
  - **htd** は CMake が必要です（Debian/Ubuntu: `sudo apt install cmake`）
- **QuickBB**: C++11 対応の g++、autotools (autoconf, automake)
- **TreeWidthSolver.jl**: Julia 1.10+（パッケージの `Project.toml` が要求）

`setup.py` はこれら（コンパイラ、`make`、`cmake`、`autoreconf`、`jar`、Boost ヘッダなど）を事前に確認し、足りないソルバーは不足しているものを表示してスキップします。

## クイックスタート

```bash
# 1. 利用可能なソルバーとベンチマークの一覧
python setup.py --list

# 2. 全てセットアップ (ダウンロード + ビルド)
python setup.py --all

# 3. 特定のソルバーだけセットアップ
python setup.py --solver flowcutter-17 --solver tamaki-2017

# 4. ベンチマークだけダウンロード
python setup.py --benchmarks-only

# 5. ベンチマーク実行
python run.py --solver all --benchmark pace2017-instances --timeout 300

# 6. 特定のソルバーで実行
python run.py --solver flowcutter-17 --benchmark pace2017-instances --timeout 60

# 7. 並列実行
python run.py --solver all --benchmark all --timeout 300 --jobs 4

# 8. クイックテスト (各ベンチマークから最大5インスタンス)
python run.py --solver all --benchmark all --timeout 60 --max-instances 5
```

## 実行オプション

`run.py` のオプション:

| オプション | 意味 |
|------------|------|
| `--solver NAME` | 実行するソルバー。複数指定可、`all` でインストール済み全部。未知の名前はエラー。 |
| `--benchmark NAME` | ベンチマークセット。複数指定可、`all` で全部。 |
| `--timeout SEC` | 1 実行あたりの実時間上限（既定 300）。独自の時間制限オプションを持つソルバーには、kill される前に結果を出せるよう少し短い内部制限を渡します。 |
| `--jobs N`, `-j N` | N 個のソルバープロセスを並列実行。 |
| `--heuristic` | heuristic コマンドを持つソルバー（tamaki-2017, tdlib-p17, jdrasil）でそれを使う。持たないソルバーは exact コマンドが走り、警告が出ます。実際に走ったモードは `mode` 列に記録されます。 |
| `--validate` | 出力された木分解を入力グラフに対して検証（頂点被覆、辺被覆、部分木の連結性、木であること、ヘッダの整合）。失敗は `status=invalid`。 |
| `--debug` | ok 以外の各実行についてコマンド、終了コード、stderr/stdout の末尾を表示。 |
| `--max-instances N` | 各ベンチマークセットの先頭 N 件だけ使う。 |
| `--output PATH` | CSV の出力先（既定 `results/YYYY-MM-DD_HHMMSS.csv`）。 |
| `--list` | インストール済みのソルバーとベンチマークを表示。 |

結果は 1 件完了するごとに CSV へ追記されるため、Ctrl-C で中断しても完了分は残り、実行中のソルバーは停止されます。並列実行が最後まで終わると投入順に並べ直されます。

### インストールマーカー

`setup.py` はクローン完了時にソルバー／ベンチマークのディレクトリへ `.tw_download_complete` を、全ビルドステップ成功時に `.tw_build_complete` を書きます。`run.py` はビルドマーカーがあるソルバーだけをインストール済みとみなします。ビルド出力はソルバーディレクトリの `.tw_build.log` に書かれます。再クローンせずにビルドし直すには `python setup.py --solver NAME` をもう一度実行してください（ディレクトリは保持され、ビルドステップだけが再実行されます）。クローンは `config/*.json` に記載のコミットに固定されています。固定コミットでクローンし直すにはディレクトリを削除してください。

## ソルバー一覧

### 厳密ソルバー (Exact)

| 名前 | 著者 | 言語 | 説明 |
|------|------|------|------|
| twalgor-tw | Hisao Tamaki | Java | Heuristic computation of exact treewidth (2022) |
| twalgor-rtw | Hisao Tamaki | Java | Contraction-recursive algorithm (2023) |
| tamaki-2017 | Tamaki et al. | Java | PACE 2017 exact track 優勝 |
| tamaki-2016 | Hisao Tamaki | C | PACE 2016 exact track 優勝 |
| tdlib-p17 | Larisch, Salfelder | C++ | TDLIB PACE 2017 submission |
| jdrasil | Bannach et al. | Java | モジュラー treewidth ソルバーフレームワーク |
| quickbb | Gogate, Dechter | C++ | 分枝限定法による厳密ソルバー |
| treewidth-solver-jl | ArrogantGao | Julia | Bouchitte-Todinca アルゴリズム (Julia) |

### ヒューリスティックソルバー (Heuristic)

| 名前 | 著者 | 言語 | 説明 |
|------|------|------|------|
| flowcutter-17 | Ben Strasser | C++ | 最大フローによるネスト分割 (PACE 2016/2017) |
| htd | Abseher et al. | C++ | 超木/木分解ライブラリ (TU Wien) |
| minfill-mrs | Jégou et al. | C++ | リスタート付き Min-fill ヒューリスティック |
| minfillbg-mrs | Jégou et al. | C++ | 二部グラフ改良版 Min-fill |

**注**: tamaki-2017, tdlib-p17, jdrasil は exact と heuristic の両方に対応しています。

## ベンチマーク一覧

| 名前 | 出典 | 説明 |
|------|------|------|
| pace2017-instances | PACE 2017 | 公式コンペティションインスタンス |
| pace2017-bonus | PACE 2017 | 追加の難問インスタンス |
| pace2016-testbed | PACE 2016 | 2016年テストベッド一式 |
| named-graphs | Lukas Larisch | 名前付きグラフ集 (Petersen, Hoffman 等) |
| control-flow-graphs | Lukas Larisch | コンパイル済みプログラムの制御フローグラフ |
| uai2014-graphs | PACE / UAI 2014 | 確率推論コンペのグラフ |
| transit-graphs | Johannes Fichte | 交通ネットワーク |
| road-graphs | Ben Strasser | 道路ネットワーク |

## 結果の形式

結果は CSV で `results/` ディレクトリに出力されます:

```
solver,mode,benchmark_set,instance,vertices,edges,treewidth,time_sec,status,memory_mb
flowcutter-17,heuristic,pace2017-instances,ex001,100,250,12,0.523,ok,41.2
tamaki-2017,exact,pace2017-instances,ex001,100,250,12,1.234,ok,312.5
```

| 列 | 意味 |
|----|------|
| `mode` | `exact` または `heuristic`。実際に走ったコマンド。 |
| `treewidth` | ソルバーが報告した幅（`status` が `ok` のときのみ）。ヒューリスティックでは上界、完了した厳密ソルバーでは厳密な treewidth。 |
| `time_sec` | ソルバープロセスの実時間（秒）。インタプリタの起動時間を含みます。Java ソルバーでは JVM 起動、TreeWidthSolver.jl では毎回の Julia パッケージの読込・コンパイル（数秒かかることがあります）が入ります。タイムアウト時は `--timeout` の値。 |
| `status` | 下表参照。 |
| `memory_mb` | ソルバーのプロセスグループ全体（ソルバー、ラッパーシェル、JVM）のピークメモリ。PSS（proportional set size）を 100ms 間隔でサンプリングするため、ごく短いピークは取りこぼすことがあります。Linux のみ。他では空欄。 |

`status` の値:

| 値 | 意味 |
|----|------|
| `ok` | ソルバーが木分解または幅を出力した（`--validate` 時は、かつ木分解が正しい）。 |
| `timeout` | `--timeout` 内に答えが出なかった。quickbb が内部制限で止まり未証明の上界しか無い場合、および kill が必要になって出力が途中で切れたヒューリスティックもこれ。 |
| `invalid` | `--validate` が出力された木分解の誤りを検出した。 |
| `parse_error` | ソルバーは正常終了したが、出力に `s td` ヘッダも幅の行も無かった。 |
| `error: exit N` / `error: signal N` | ソルバーが非ゼロで終了、またはシグナルで死んだ（クラッシュ、メモリ不足）。 |
| `error: <メッセージ>` | ランナー側の失敗。例: インスタンスファイルをパースできなかった。 |

## テスト

純 Python のヘルパー（パース、フォーマット変換、木分解の検証）に対する単体テストは、
`tests/` 内の小さな参照グラフ（`k4.gr`, `cycle5.gr`, `path4.gr`）を用いて実行でき、
ソルバーのインストールは不要です:

```bash
pytest tests/            # または: python tests/test_libs.py
```

## PACE .gr フォーマット

入力グラフの標準形式:

```
c コメント (省略可)
p tw <頂点数> <辺数>
<u> <v>
```

頂点は 1-indexed です。

## ライセンス

このリポジトリはソルバーやベンチマークのソースコードを再配布していません。全ての外部コードはセットアップ時に `git clone` でダウンロードされます。各ソルバー・ベンチマークは個別のライセンスに従います：

### ソルバーのライセンス

| ソルバー | ライセンス | リポジトリ |
|----------|-----------|------------|
| twalgor-tw | GPL-3.0 | [twalgor/tw](https://github.com/twalgor/tw) |
| twalgor-rtw | GPL-3.0 | [twalgor/RTW](https://github.com/twalgor/RTW) |
| tamaki-2017 | MIT | [TCS-Meiji/PACE2017-TrackA](https://github.com/TCS-Meiji/PACE2017-TrackA) |
| tamaki-2016 | MIT | [TCS-Meiji/treewidth-exact](https://github.com/TCS-Meiji/treewidth-exact) |
| tdlib-p17 | 未指定 | [freetdi/p17](https://github.com/freetdi/p17) |
| jdrasil | MIT | [maxbannach/Jdrasil](https://github.com/maxbannach/Jdrasil) |
| quickbb | GPL-2.0 | [dechterlab/quickbb](https://github.com/dechterlab/quickbb) |
| treewidth-solver-jl | MIT | [ArrogantGao/TreeWidthSolver.jl](https://github.com/ArrogantGao/TreeWidthSolver.jl) |
| flowcutter-17 | BSD-2-Clause | [kit-algo/flow-cutter-pace17](https://github.com/kit-algo/flow-cutter-pace17) |
| htd | GPL-3.0 | [mabseher/htd](https://github.com/mabseher/htd) |
| minfill-mrs | GPL-3.0 | [td-mrs/minfill_mrs](https://github.com/td-mrs/minfill_mrs) |
| minfillbg-mrs | GPL-3.0 | [td-mrs/minfillbg_mrs](https://github.com/td-mrs/minfillbg_mrs) |

### ベンチマークのライセンス

| ベンチマーク | ライセンス | リポジトリ |
|-------------|-----------|------------|
| pace2017-instances | CC | [PACE-challenge/Treewidth-PACE-2017-instances](https://github.com/PACE-challenge/Treewidth-PACE-2017-instances) |
| pace2017-bonus | CC | [PACE-challenge/Treewidth-PACE-2017-bonus-instances](https://github.com/PACE-challenge/Treewidth-PACE-2017-bonus-instances) |
| pace2016-testbed | GPL-3.0 | [holgerdell/PACE-treewidth-testbed](https://github.com/holgerdell/PACE-treewidth-testbed) |
| named-graphs | 未指定 | [freetdi/named-graphs](https://github.com/freetdi/named-graphs) |
| control-flow-graphs | CC | [freetdi/CFGs](https://github.com/freetdi/CFGs) |
| uai2014-graphs | CC | [PACE-challenge/UAI-2014-competition-graphs](https://github.com/PACE-challenge/UAI-2014-competition-graphs) |
| transit-graphs | 未指定 | [daajoe/transit_graphs](https://github.com/daajoe/transit_graphs) |
| road-graphs | Public Domain / ODbL | [ben-strasser/road-graphs-pace16](https://github.com/ben-strasser/road-graphs-pace16) |

## 参考リンク

- [PACE Challenge](https://pacechallenge.org/)
- [PACE Treewidth Collection](https://github.com/PACE-challenge/Treewidth)
- [td-validate (検証ツール)](https://github.com/holgerdell/td-validate)
