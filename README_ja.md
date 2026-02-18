# AI生成 Treewidth Solver Benchmark Suite

> **注意**: 本リポジトリのコード、ドキュメント、設定ファイルを含むすべての内容は、AI (Claude) によって生成されたものです。人間が手作業で記述した部分はありません。

[English](README.md)

複数の公開されている treewidth ソルバーを統一的なインターフェースでベンチマーク比較するためのツールキットです。

## 前提条件

必須:
- Python 3.8+
- Git

ソルバーごとの依存:
- **Java ソルバー** (twalgor-tw, twalgor-rtw, tamaki-2017, tamaki-2016, jdrasil): JDK 8+
- **C++ ソルバー** (tdlib-p17, flowcutter-17, htd, minfill-mrs, minfillbg-mrs): GCC 4.8+
  - **tdlib-p17** は Boost と autotools が必要です（Debian/Ubuntu: `sudo apt install libboost-graph-dev autoconf automake`）
  - **htd** は CMake が必要です（Debian/Ubuntu: `sudo apt install cmake`）
- **QuickBB**: GCC, autotools (autoconf, automake)
- **TreeWidthSolver.jl**: Julia 1.6+

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
solver,benchmark_set,instance,vertices,edges,treewidth,time_sec,status,memory_mb
flowcutter-17,pace2017-instances,ex001,100,250,12,0.523,ok,
tamaki-2017,pace2017-instances,ex001,100,250,12,1.234,ok,
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
