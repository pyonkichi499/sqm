# ディレクトリ構成
```
├── calc_bh.py
├── complex_Langevin_BH.f90
├── functions_module.mod
├── params.dat
├── read_dat.py
├── read_dat_mod.py
├── README.md
└── wparams.py
```
* calc_bh.py
  * メインで使うファイル
  * 計算回すときに実行する

* complex_Langevin_BH.f90
  * fortranのコード
* functions_module.mod

  * FORTRANのメイン関数(complex_Langevin_BH.f90)の外で関数を定義してあるのでコンパイル時に自動で作られるファイル
  * 自作のfunctions_moduleの情報が入っている(はず)
  * バイナリ
* params.dat
  * 各パラメータの値を書いてあるファイル
  * read_dat.pyが読み込む
* read_dat.py
  * read_dat_mod.pyの原型
  * 今は使ってない
* read_dat_mod.py
  * complex_Langevin_BH.f90で作ったdatファイルを読むのに使う(calc_bh.pyが呼ぶ)
* README.md

  * この解説
* wparams.py
  * params.datを書くのに使う(calc_bh.pyが呼ぶ)

# 使い方
* 前提
  * gfortranとpythonが動く環境
1. complex_Langevin_BH.f90をコンパイル
  
```
$ gfortran complex_Langevin_BH.f90
```

1. calc_bh.pyを実行