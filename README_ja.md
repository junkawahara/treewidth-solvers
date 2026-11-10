# AI生成 Treewidth Solver Benchmark Suite

> **注意**: 本リポジトリのコード、ドキュメント、設定ファイルを含むすべての内容は、AI (Claude) によって生成されたものです。人間が手作業で記述した部分はありません。

[English](README.md)

複数の公開されている treewidth ソルバーを統一的なインターフェースでベンチマーク比較するためのツールキットです。

## 前提条件

必須:
- Python 3.8+
- Git

ソルバーごとの依存:
- **Java ソルバー** (twalgor-tw, twalgor-rtw, tamaki-2017, jdrasil, jdrasil-approx, turbocharge-2016, libtw): JDK 8+
- **C/C++ ソルバー** (tamaki-2016, tdlib-p17, flowcutter-17, flowcutter-16, htd, minfill-mrs, minfillbg-mrs, cvo2, foxepstein-2016, iitm-2016, triangulator, triangulator-msc, treedec, halin-tw, bfk-treewidth-2approx, tamaki-treewidth-sea2019, flowcutter-kahip): GCC 7+（C++17 対応の g++）と `make`
  - **treedec** は Boost（graph と thread）、autotools、libtool、Git が必要（Debian/Ubuntu では `sudo apt install libboost-graph-dev libboost-thread-dev autoconf automake libtool`）。依存する gala ヘッダはビルド時に clone します
  - **tdlib-p17** は C++17（ビルド時にインライン変数を挿入します）、Boost、autotools、libtool が必要です（Debian/Ubuntu: `sudo apt install libboost-graph-dev libboost-thread-dev autoconf automake libtool`）
  - **htd**、**cvo2**、**flowcutter-kahip** は CMake が必要です（Debian/Ubuntu: `sudo apt install cmake`）。**flowcutter-kahip** はビルド時に KaHIP を clone するので Git も必要です
  - **tamaki-treewidth-sea2019** は C++20 が必要です（`-std=c++20`、GCC 10 以上）
- **QuickBB**: C++11 対応の g++、autotools (autoconf, automake)
- **Rust ソルバー** (arboretum, goatd): `cargo` を含む Rust ツールチェーン（<https://rustup.rs>）。goatd は Rust 1.88+ と、同梱の FlowCutter をビルドするための C++20 コンパイラ（g++ 12+）が必要です
- **bz-treewidth**: .NET SDK 8 以上（`dotnet`、例: `sudo apt install dotnet-sdk-8.0`）。上流の Mono ベースの Makefile は使いません
- **TreeWidthSolver.jl, CliqueTrees.jl**: Julia 1.10+（パッケージの `Project.toml` が要求）
- **passagemath**: Python 3.11+ と `venv`、Python ヘッダ、`gcc`（Debian/Ubuntu では `sudo apt install python3-venv python3-dev`）。ビルド時に約 110 MB の wheel をダウンロードし、約 430 MB の venv を作ります

`setup.py` はこれら（コンパイラ、`make`、`cmake`、`autoreconf`、`jar`、`cargo`、`dotnet`、Boost ヘッダなど）を事前に確認し、足りないソルバーは不足しているものを表示してスキップします。

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

`setup.py` はクローン完了時にソルバー／ベンチマークのディレクトリへ `.tw_download_complete` を、全ビルドステップ成功時に `.tw_build_complete` を書きます。`run.py` はビルドマーカーがあるソルバーだけをインストール済みとみなします。ビルド出力はソルバーディレクトリの `.tw_build.log` に書かれます。再クローンせずにビルドし直すには `python setup.py --solver NAME` をもう一度実行してください（ディレクトリは保持され、ビルドステップだけが再実行されます）。クローンは `config/*.json` に記載のコミットに固定されています。固定コミットでクローンし直すにはディレクトリを削除してください。passagemath はクローンせず `solvers/passagemath/venv` に pip でインストールし、全パッケージの版を `config/passagemath-constraints.txt` で固定しています。venv はセットアップのたびに作り直します。

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
| bz-treewidth | Bodlaender, van der Zanden | C# | 安全セパレータ付き部分集合 DP（PACE 2016 exact track 2 位） |
| arboretum | Johannes Meintrup | Rust | 安全セパレータ付き positive-instance-driven DP。タブー探索ヒューリスティックも持つ |
| cliquetrees-jl | Richard Samuelson | Julia | CliqueTrees.jl: safe rules/separators 付き PIDBT。min-fill ヒューリスティックも持つ |
| libtw | van Dijk, van den Heuvel, Slob | Java | LibTW (2006): 部分集合 DP。greedy fill-in ヒューリスティックも持つ |
| triangulator | Tuukka Korhonen | C++ | Triangulator: 列挙した potential maximal clique 上の Bouchitte-Todinca DP（PACE 2017 minimum fill-in track 2 位） |
| triangulator-msc | Tuukka Korhonen | C++ | Triangulator の 2020 年修士論文版。同じアルゴリズムに前処理と高速な PMC 列挙を加えたもの。CPLEX/MaxHS 抜きでビルド（`config/triangulator-msc-no-cplex.patch`） |
| treedec | Larisch, Salfelder | C++ | treedec (tdlib) の 2025 年版を `tdecomp` ドライバ経由で実行。`--ex17` は前処理 + Tamaki 厳密法。`--ppfitm`（前処理 + fill-in + 三角化最小化）ヒューリスティックも持つ |
| passagemath | The Sage Developers | Python/Cython | SageMath 自前の厳密法 `Graph.treewidth(algorithm='sage')`（カットと連結成分の DP）。pip で入る passagemath-graphs を使用 |
| halin-tw | Jun Kawahara | C++ | Halin グラフ専用。Eppstein の線形時間認識のあと、Alejandro-Soto, Trejo-Sanchez, Segura (2025) の線形時間アルゴリズム H-Td で幅 3 の木分解を作る。それ以外のグラフは受け付けない（`not_applicable`） |
| tamaki-treewidth-sea2019 | Jun Kawahara | C++ | Tamaki (SEA 2019) のアルゴリズムを講演スライドから再実装したもの。極小分離集合の厳密リストとヒューリスティックリストの上で msDP を行い、下からの探索と上からの探索を交互に進める（`-m alternate`） |

### ヒューリスティックソルバー (Heuristic)

| 名前 | 著者 | 言語 | 説明 |
|------|------|------|------|
| flowcutter-17 | Ben Strasser | C++ | 最大フローによるネスト分割 (PACE 2016/2017) |
| htd | Abseher et al. | C++ | 超木/木分解ライブラリ (TU Wien) |
| minfill-mrs | Jégou et al. | C++ | リスタート付き Min-fill ヒューリスティック |
| minfillbg-mrs | Jégou et al. | C++ | 二部グラフ改良版 Min-fill |
| flowcutter-16 | Ben Strasser | C++ | PACE 2016 提出版 FlowCutter（heuristic sequential track 優勝） |
| cvo2 | Kask, Lam | C++ | ランダム化 min-fill 順序のマルチスレッド探索（PACE 2016 heuristic parallel track 優勝） |
| foxepstein-2016 | Eli Fox-Epstein | C++ | Minimum-degree / minimum-fill-in（PACE 2016 heuristic track 2 位） |
| turbocharge-2016 | Gaspers et al. | Java | 貪欲ヒューリスティックの turbocharging（PACE 2016 heuristic track 4 位） |
| iitm-2016 | Joglekar, Kamble, Pandian | C++ | サイクル除去による弦グラフ化（PACE 2016 heuristic track 6 位） |
| goatd | Guy Van den Broeck | Rust | 消去順序・nested dissection・FlowCutter を一つの時間予算で回すポートフォリオ (2026) |
| bfk-treewidth-2approx | Jun Kawahara | C++ | Belbasi, Fürer, Kumar (2024) の最適化 2 近似。min-degree の木分解のバッグを、グループ化した木分解上の DP で分割して幅 2·tw+1 以下にする。DP がメモリに収まるのは min-degree の幅が小さいとき（ベンチマークでは 14 以下）だけ |
| jdrasil-approx | Bannach, Berndt, Ehlers | Java | Jdrasil の近似モード（`jdrasil.Approximation`）。縮約規則と safe separator で分割したあと、各 atom に Robertson–Seymour の FPT 近似をかけ、探索が棄却しなかった最初の k について幅 4k+4 以下の分解を作る。atom で失敗したときに 1 つのバッグで答えるのをやめ、エラーで終わるようにパッチを当てている（`config/jdrasil-approx-fail-loudly.patch`） |
| flowcutter-kahip | Hamann, Strasser、KaHIP: Sanders, Schulz ら | C++ | FlowCutter の実験用コード（ALENEX 2016）を KaHIP v3.25 付きでビルドしたもの。FlowCutter の CCH 用前処理のあと、KaHIP の頂点分離で nested dissection を行う。計算した順序が実際に使われるようにパッチを当てている（`config/flowcutter-kahip.patch`） |

**注**: tamaki-2017, tdlib-p17, jdrasil, arboretum, cliquetrees-jl, libtw, treedec は exact と heuristic の両方に対応しています。

ソルバー固有の事情（ビルドに必要なソースの修正、どの上流バリアントをビルドしているか、出力の癖）は `config/solvers.json` の各エントリの `notes` に記録しています。結果を読む前に知っておくべき点:

- **cvo2** は CPU コアを 1 つ残して全部使うので、他と比較する際は注意してください（単独で走らせるのが無難です）。
- **iitm-2016** は最初の弦グラフ化が終わるまで SIGTERM に対して自明な 1 バッグ分解を返します。PACE 2017 インスタンスでは 1 分以上かかるため、短いタイムアウトでは幅 n-1 が記録されます。
- **libtw** と **quickbb** は幅だけを出力しバッグを出さないので、`--validate` では検証できません。libtw の厳密アルゴリズムは全頂点部分集合を保持するため、小さいグラフでしか終わりません。
- **triangulator-msc** の上流は幅しか出力しません。`config/` のパッチで `.td` 出力を追加し、runner が使わない CPLEX/MaxHS 依存のモード（ハイパー木幅、MaxSAT による系統解析）を外しています。
- **treedec** には各インスタンスの単純グラフ化コピー（自己ループ・多重辺・コメント・空行を除去）を渡します。リーダーが空行と自己ループで落ちるためで、transit-graphs には自己ループとコメントの両方が含まれます。exact モードは PACE 2017 の方式を現行ライブラリで組み直したものなので、2017 年当時の提出物をそのまま動かす tdlib-p17 と比較してください。
- **jdrasil** にも、両モードとも同じ単純グラフ化コピーを渡します。リーダーが自己ループ `u u` を辺として読み、その頂点を自分自身の隣接頂点にしてしまうため、自己ループを含む唯一のセットである transit-graphs（3133 件中 1378 件）の一部で誤動作します。その 1378 件（60 秒、`--validate`）では、元のファイルのままだと exact モードは 320 件で例外で止まり（`parse_error` と記録）、11 件で妥当でない木分解を出力しました。また `ok` の 597 件のうち 99 件は木幅より 1〜6 大きい幅でした（tamaki-2017 の厳密な幅で確認）。コピーを渡すと 648 件に答え（すべて妥当）、残りは時間切れでした。ヒューリスティックモード（10 秒）は、元のファイルでは 1353 件で例外で止まり、コピーでは 1378 件すべてに答えました。
- **passagemath** は tdlib ではなく Sage 自前のアルゴリズムを使います（passagemath-tdlib があると Sage は tdlib を選びますが、それは tdlib-p17 と treedec で既にカバーしています）。小さなグラフ以外では PACE のソルバーよりずっと遅く、tamaki-2017 が 0.3 秒で解く BrinkmannGraph に 50 秒、CoxeterGraph に 119 秒かかります。
- **halin-tw** は Halin グラフだけを線形時間で解き、それ以外のグラフは受け付けません（終了コード 2。`not_applicable` として記録）。ベンチマーク 6036 件のうち受け付けるのは 9 件（FruchtGraph、TetrahedralGraph、2 か所にある WheelGraph_100、transit-graphs 中の 5 頂点の車輪 5 件）で、どれも treewidth 3 です。平面性にもとづく独立な判定でも同じ 9 件になります。したがって `ok` の行は少なく、`not_applicable` の行は失敗ではありません。
- **bfk-treewidth-2approx** の答えは常に幅 2·tw+1 以下ですが、そのための DP は各ノードに 3^|バッグ| か 4^|バッグ| 要素の表を持つので、改善できるのは min-degree の木分解の幅が小さいグラフに限られます。ベンチマークで改善できた最大の幅は 14 で、下に書く終了コード 3 は road-graphs 以外ではどれも幅 14 以上でした（上流の README は限界を 16 程度としています）。表が 24 GB の上限（`--mem-gb`）を超える場合は計算をやめて終了コード 3 で終わり、`error: exit 3` と記録されます。これはソルバーが諦めたのであって、クラッシュではありません。min-degree の幅がはじめから 2·退化度+1 以下なら、DP をせずにその木分解をそのまま出力します。ベンチマーク全 8 セット（6036 件、60 秒、`--validate`）では `ok` が 4636 件（すべて妥当）でしたが、そのうち min-degree より幅が小さいのは 30 件だけで、1252 件が終了コード 3、148 件が時間切れでした。1 回の実行で 24 GB 近く使うことがある（観測値 22.9 GB）ので、`--jobs` では 1 ジョブあたりその分のメモリを見込んでください。
- **tamaki-treewidth-sea2019** は Tamaki の SEA 2019 のアルゴリズムを講演スライドから組み立て直した再実装で（論文は入手できなかったため）、Tamaki 本人のコードではありません。隣接関係を頂点ごとに n ビットの集合で持つので、グラフを読み込むだけで n²/8 バイト（20 万頂点で 5 GB、100 万頂点で 125 GB）を使い、ソルバー自身はメモリの上限を設けません。PACE 2017 heuristic track のグラフや road-graphs に対しては、ジョブ数を減らすか、`ulimit -v` などで 1 プロセスごとのメモリ上限をかけてください。以下の数字は `ulimit -v` で 1 プロセス 5 GiB、8 ジョブで測ったものです。ベンチマーク全 8 セット（6036 件、60 秒、`--validate`）では 4795 件が `ok`（すべて妥当）、1201 件が時間切れで、残る 40 件（15 万 4188 頂点以上のグラフはすべてここに入ります）は上限で止まりました（読み込み中にグラフが収まらなかった場合は `error: exit 1`、計算中に上限に達した場合は `error: exit 134`）。この 40 件のうち 31 万頂点以下の 11 件は、上限を 20 GiB にしても 60 秒以内に終わりませんでした。残りの 5996 件では、このソルバーと tamaki-2017 の両方が解いたものが 4560 件で幅はすべて一致し、このソルバーだけが解いたものが 235 件（うち transit-graphs 155 件、pace2017-bonus 26 件）、tamaki-2017 だけが解いたものが 21 件でした。その 235 件を triangulator-msc（60 秒）でも解くと 17 件が解けて幅は一致し、残る 218 件は他の厳密ソルバーの答えと照合できていません。
- **bz-treewidth** は上流 Makefile の先頭にある `BZTreewidth-DP` バリアントを Mono ではなく .NET SDK でビルドします。残り 11 バリアントはプリプロセッサシンボルの違いです。
- **jdrasil-approx** の答えは、探索が棄却しなかった最初の k について幅 4k+4 以下です。k は探索が誤って諦めない限り tw 以下です（上流のコードは誤って諦めることを許していますが、観測はされていません）。以下の数字は 1 プロセスあたり `-Xmx3g`、8 ジョブで測ったものです（新しい 2 ソルバーを合わせて合計 26.3 GiB 以下）。ベンチマーク全 8 セット（6036 件、60 秒、`--validate`）では 4510 件が `ok`（すべて妥当）、1509 件が時間切れで、解けた最大のグラフは 6940 頂点でした。`error: exit 1` の 17 件は、再帰による切断点の探索が Java のスタックを溢れさせた 7865〜1 万 7307 頂点の PACE 2017 heuristic track のグラフ 9 件（試した 1 件は `-Xss` を大きくしても時間切れになっただけでした）と、3 GB のヒープに収まらない 470 万頂点以上のグラフ 8 件です。既知の木幅（同梱の最適な木分解がある PACE 2017 exact の 200 件、instances.csv に木幅がある PACE 2017 bonus の 91 件、tamaki-2017 が解いた named-graphs の 113 件）と比べると、それぞれ 73 件、12 件、101 件を解き、幅が 4·tw+4 を超えたものはなく、tw との差は最大 16、13、10 でした。
- **flowcutter-kahip** は FlowCutter の実験用コードで、PACE の提出物ではありません。上流は出力時に計算した順序を使わず、バッグの頂点をその順序での位置の番号で書いていたため（出力は妥当な木分解になりませんでした）、また辺のないグラフではクラッシュしていました。`config/flowcutter-kahip.patch` で両方を直しています。KaHIP は `-march=native` でコンパイルされるので、バイナリはビルドした CPU に依存します。ソルバー自身は時間の上限を持たず、SIGTERM を受けても何も出力しません。以下の数字は `ulimit -v` で 1 プロセス 3.5 GB、8 ジョブで測ったものです。ベンチマーク全 8 セット（6036 件、60 秒、`--validate`）では 5540 件が `ok`（すべて妥当）、488 件が時間切れ、8 件が `error: exit 139` でした。8 件のうち 1 件は辺のないグラフ two-vertices で、パッチに修正を加える前のクラッシュです。修正後に pace2016-testbed を測り直すと `ok` になり、幅はどれも変わりませんでした。残る 7 件は 17 万 8719 頂点以上のグラフでメモリの上限に達したもので、確保に失敗するとクラッシュします。上限なしでは he192（17 万 8719 頂点）は 4.6 GB を使い、120 秒以内に終わりませんでした。同じ既知の木幅と比べると、それぞれ 180 件、91 件、113 件を解き、tw との差は最大 32、11、6（中央値 4、5、1）でした。jdrasil-approx と両方が解いた 4495 件では、このソルバーの幅が小さいものが 861 件、大きいものが 881 件でした。control-flow-graphs では 1817 件中 186 件で大きく、PACE 2017 exact では両方が解いた 64 件中 59 件で小さくなっています。

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
| `time_sec` | ソルバープロセスの実時間（秒）。インタプリタの起動時間を含みます。Java ソルバーでは JVM 起動、TreeWidthSolver.jl と CliqueTrees.jl では毎回の Julia パッケージの読込・コンパイル（10〜15 秒）が入ります。タイムアウト時は `--timeout` の値。 |
| `status` | 下表参照。 |
| `memory_mb` | ソルバーのプロセスグループ全体（ソルバー、ラッパーシェル、JVM）のピークメモリ。PSS（proportional set size）を 100ms 間隔でサンプリングするため、ごく短いピークは取りこぼすことがあります。Linux のみ。他では空欄。 |

`status` の値:

| 値 | 意味 |
|----|------|
| `ok` | ソルバーが木分解または幅を出力した（`--validate` 時は、かつ木分解が正しい）。 |
| `timeout` | `--timeout` 内に答えが出なかった。quickbb が内部制限で止まり未証明の上界しか無い場合、および kill が必要になって出力が途中で切れたヒューリスティックもこれ。 |
| `invalid` | 出力された木分解に誤りがある。`treewidth` 列は `s td` ヘッダの値なので、ヘッダの幅と最大バッグのサイズは常に照合します。`--validate` を付けると、入力グラフに対する検証も行います。理由は `--debug` で表示されます。 |
| `parse_error` | ソルバーは正常終了したが、出力に `s td` ヘッダも幅の行も無かった。 |
| `not_applicable` | 特定のグラフクラス専用のソルバーが、インスタンスをそのクラス外として受け付けなかった。`not_applicable_exit_code` で宣言された終了コードで判定します（halin-tw: Halin グラフでない）。 |
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

このリポジトリはソルバーやベンチマークのソースコードを再配布していません。全ての外部コードはセットアップ時に `git clone` でダウンロードされます（passagemath だけは PyPI から `pip` でインストールします）。各ソルバー・ベンチマークは個別のライセンスに従います：

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
| flowcutter-16 | BSD-2-Clause | [ben-strasser/flow-cutter-pace16](https://github.com/ben-strasser/flow-cutter-pace16) |
| cvo2 | MIT | [willmlam/CVO2](https://github.com/willmlam/CVO2) |
| foxepstein-2016 | GPL-3.0 | [efoxepstein/2016-pace-challenge](https://github.com/efoxepstein/2016-pace-challenge) |
| turbocharge-2016 | MIT | [mfjones/pace2016](https://github.com/mfjones/pace2016) |
| iitm-2016 | GPL-2.0 | [mrprajesh/pacechallenge](https://github.com/mrprajesh/pacechallenge) |
| bz-treewidth | MIT | [TomvdZanden/BZTreewidth](https://github.com/TomvdZanden/BZTreewidth) |
| arboretum | MIT | [jmeintrup/arboretum](https://github.com/jmeintrup/arboretum) |
| goatd | Apache-2.0 | [Tractables/goatd](https://github.com/Tractables/goatd) |
| cliquetrees-jl | MIT | [AlgebraicJulia/CliqueTrees.jl](https://github.com/AlgebraicJulia/CliqueTrees.jl) |
| libtw | LGPL-2.1 | [WPettersson/libtw](https://github.com/WPettersson/libtw)（treewidth.com のミラー） |
| triangulator | MIT | [Laakeri/Triangulator](https://github.com/Laakeri/Triangulator) |
| triangulator-msc | MIT | [Laakeri/triangulator-msc](https://github.com/Laakeri/triangulator-msc) |
| passagemath | GPL-2.0-or-later | [passagemath/passagemath](https://github.com/passagemath/passagemath)（PyPI: [passagemath-graphs](https://pypi.org/project/passagemath-graphs/)） |
| treedec | GPL-2.0 / GPL-3.0（ファイルごと） | [freetdi/treedec](https://codeberg.org/freetdi/treedec)（ミラー: [freetdi/tdlib](https://github.com/freetdi/tdlib)）。gala ヘッダは GPL-3.0、[freetdi/gala](https://github.com/freetdi/gala) |
| halin-tw | MIT | [junkawahara/halin_tw](https://github.com/junkawahara/halin_tw) |
| bfk-treewidth-2approx | MIT | [junkawahara/bfk-treewidth-2approx](https://github.com/junkawahara/bfk-treewidth-2approx) |
| tamaki-treewidth-sea2019 | MIT | [junkawahara/tamaki-treewidth-sea2019](https://github.com/junkawahara/tamaki-treewidth-sea2019) |
| jdrasil-approx | MIT | [maxbannach/Jdrasil](https://github.com/maxbannach/Jdrasil) |
| flowcutter-kahip | BSD-3-Clause、KaHIP は MIT | [kit-algo/flow-cutter](https://github.com/kit-algo/flow-cutter)、KaHIP: [KaHIP/KaHIP](https://github.com/KaHIP/KaHIP) |

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
