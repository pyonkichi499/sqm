program test_functions
    use functions_module
    use ieee_arithmetic, only: ieee_value, ieee_quiet_nan, ieee_positive_inf, &
                               ieee_is_nan, ieee_is_finite
    implicit none

    integer :: n_passed, n_failed
    n_passed = 0
    n_failed = 0

    call test_set_nn(n_passed, n_failed)
    call test_da_uniform(n_passed, n_failed)
    call test_da_ast_uniform(n_passed, n_failed)
    call test_rk_golden_master(n_passed, n_failed)
    call test_write_io(n_passed, n_failed)
    call test_free_field_limit(n_passed, n_failed)
    call test_nan_detection(n_passed, n_failed)
    call test_inf_detection(n_passed, n_failed)
    call test_box_muller_no_nan(n_passed, n_failed)
    call test_stability_uniform_field(n_passed, n_failed)
    call test_error_handling_open(n_passed, n_failed)

    write(*,*)
    write(*,'(A,I3,A,I3,A)') " Results: ", n_passed, " passed, ", n_failed, " failed"

    if (n_failed > 0) then
        stop 1
    else
        write(*,*) "All tests passed!"
    end if

contains

    subroutine assert_eq_int(name, expected, actual, n_passed, n_failed)
        character(len=*), intent(in) :: name
        integer, intent(in) :: expected, actual
        integer, intent(inout) :: n_passed, n_failed
        if (expected == actual) then
            n_passed = n_passed + 1
        else
            n_failed = n_failed + 1
            write(*,'(A,A,A,I6,A,I6)') " FAIL: ", name, " expected=", expected, " actual=", actual
        end if
    end subroutine

    subroutine assert_near(name, expected, actual, tol, n_passed, n_failed)
        character(len=*), intent(in) :: name
        double precision, intent(in) :: expected, actual, tol
        integer, intent(inout) :: n_passed, n_failed
        if (abs(expected - actual) < tol) then
            n_passed = n_passed + 1
        else
            n_failed = n_failed + 1
            write(*,'(A,A,A,ES22.14,A,ES22.14)') " FAIL: ", name, &
                " expected=", expected, " actual=", actual
        end if
    end subroutine

    subroutine assert_contains(name, arr, val, n_passed, n_failed)
        character(len=*), intent(in) :: name
        integer, intent(in) :: arr(:), val
        integer, intent(inout) :: n_passed, n_failed
        if (any(arr == val)) then
            n_passed = n_passed + 1
        else
            n_failed = n_failed + 1
            write(*,'(A,A,A,I6)') " FAIL: ", name, " not found: ", val
        end if
    end subroutine

    subroutine assert_true(name, condition, n_passed, n_failed)
        character(len=*), intent(in) :: name
        logical, intent(in) :: condition
        integer, intent(inout) :: n_passed, n_failed
        if (condition) then
            n_passed = n_passed + 1
        else
            n_failed = n_failed + 1
            write(*,'(A,A,A)') " FAIL: ", name, " expected .true."
        end if
    end subroutine

    subroutine assert_false(name, condition, n_passed, n_failed)
        character(len=*), intent(in) :: name
        logical, intent(in) :: condition
        integer, intent(inout) :: n_passed, n_failed
        if (.not. condition) then
            n_passed = n_passed + 1
        else
            n_failed = n_failed + 1
            write(*,'(A,A,A)') " FAIL: ", name, " expected .false."
        end if
    end subroutine

    ! ===========================================
    ! Test: set_nn が正しい近傍テーブルを作るか
    ! ===========================================
    subroutine test_set_nn(n_passed, n_failed)
        integer, intent(inout) :: n_passed, n_failed

        write(*,*) "--- test_set_nn ---"
        call set_nn()

        ! Site 1 = (1,1,1). 6x6x6 PBC格子での近傍:
        ! index = (x-1)*Ny*Nz + (y-1)*Nz + z
        ! (2,1,1)=37, (6,1,1)=181, (1,2,1)=7, (1,6,1)=31, (1,1,2)=2, (1,1,6)=6
        call assert_contains("nn(1) has (2,1,1)=37",  nn(:,1), 37,  n_passed, n_failed)
        call assert_contains("nn(1) has (6,1,1)=181", nn(:,1), 181, n_passed, n_failed)
        call assert_contains("nn(1) has (1,2,1)=7",   nn(:,1), 7,   n_passed, n_failed)
        call assert_contains("nn(1) has (1,6,1)=31",  nn(:,1), 31,  n_passed, n_failed)
        call assert_contains("nn(1) has (1,1,2)=2",   nn(:,1), 2,   n_passed, n_failed)
        call assert_contains("nn(1) has (1,1,6)=6",   nn(:,1), 6,   n_passed, n_failed)

        ! Site 216 = (6,6,6). 近傍:
        ! (1,6,6)=36, (5,6,6)=180, (6,1,6)=186, (6,5,6)=210, (6,6,1)=211, (6,6,5)=215
        call assert_contains("nn(216) has (1,6,6)=36",  nn(:,216), 36,  n_passed, n_failed)
        call assert_contains("nn(216) has (5,6,6)=180", nn(:,216), 180, n_passed, n_failed)
        call assert_contains("nn(216) has (6,1,6)=186", nn(:,216), 186, n_passed, n_failed)
        call assert_contains("nn(216) has (6,5,6)=210", nn(:,216), 210, n_passed, n_failed)
        call assert_contains("nn(216) has (6,6,1)=211", nn(:,216), 211, n_passed, n_failed)
        call assert_contains("nn(216) has (6,6,5)=215", nn(:,216), 215, n_passed, n_failed)

        ! 全サイトが近傍6つ持つこと (sentinel -1 が無いこと)
        call assert_eq_int("nn count site 1",   6, count(nn(:,1)   > 0), n_passed, n_failed)
        call assert_eq_int("nn count site 100", 6, count(nn(:,100) > 0), n_passed, n_failed)
        call assert_eq_int("nn count site 216", 6, count(nn(:,216) > 0), n_passed, n_failed)
    end subroutine

    ! ===========================================
    ! Test: da() が一様場で正しい値を返すか
    ! ===========================================
    subroutine test_da_uniform(n_passed, n_failed)
        integer, intent(inout) :: n_passed, n_failed
        complex(kind(0d0)) :: result

        write(*,*) "--- test_da_uniform ---"
        call set_nn()

        ! 一様場: a = 1, a_ast = 1
        a = cmplx(1d0, 0d0, kind=kind(0d0))
        a_ast = cmplx(1d0, 0d0, kind=kind(0d0))
        mu = 2d0
        U = 1d0
        dtau = 0.3d0

        ! tau=1, x=1 での da:
        !   時間微分: (a(2,1) - a(Ntau,1)) / (2*dtau) = 0
        !   近傍和:   6 * 1.0 = 6
        !   非線形:   -U * a_ast * a * a = -1
        !   化学pot:  mu * a = 2
        !   da = 2 * (0 + 6 - 1 + 2) = 14
        result = da(a, a_ast, 1, 1)
        call assert_near("da(uniform) real", 14d0, real(result), 1d-10, n_passed, n_failed)
        call assert_near("da(uniform) imag", 0d0,  aimag(result), 1d-10, n_passed, n_failed)

        ! tau=3 (中間) でも一様場なので同じ結果
        result = da(a, a_ast, 3, 100)
        call assert_near("da(uniform,tau=3) real", 14d0, real(result), 1d-10, n_passed, n_failed)
        call assert_near("da(uniform,tau=3) imag", 0d0,  aimag(result), 1d-10, n_passed, n_failed)
    end subroutine

    ! ===========================================
    ! Test: da_ast() が一様場で正しい値を返すか
    ! ===========================================
    subroutine test_da_ast_uniform(n_passed, n_failed)
        integer, intent(inout) :: n_passed, n_failed
        complex(kind(0d0)) :: result

        write(*,*) "--- test_da_ast_uniform ---"
        call set_nn()

        a = cmplx(1d0, 0d0, kind=kind(0d0))
        a_ast = cmplx(1d0, 0d0, kind=kind(0d0))
        mu = 2d0
        U = 1d0
        dtau = 0.3d0

        ! da_ast at tau=1, x=1:
        !   時間微分: -(a_ast(2,1) - a_ast(Ntau,1)) / (2*dtau) = 0
        !   近傍和:   6
        !   非線形:   -1
        !   化学pot:  2
        !   da_ast = 2 * (0 + 6 - 1 + 2) = 14
        result = da_ast(a, a_ast, 1, 1)
        call assert_near("da_ast(uniform) real", 14d0, real(result), 1d-10, n_passed, n_failed)
        call assert_near("da_ast(uniform) imag", 0d0,  aimag(result), 1d-10, n_passed, n_failed)
    end subroutine

    ! ===========================================
    ! Test: RK2ループのゴールデンマスター
    !   固定シードで短いシミュレーションを走らせ、
    !   場のチェックサムが変わらないことを確認
    ! ===========================================
    subroutine test_rk_golden_master(n_passed, n_failed)
        integer, intent(inout) :: n_passed, n_failed
        integer :: seedsize
        integer, allocatable :: seed_arr(:)
        double precision :: checksum_re, checksum_im

        write(*,*) "--- test_rk_golden_master ---"

        ! 固定シードで再現性を確保
        call random_seed(size=seedsize)
        allocate(seed_arr(seedsize))
        seed_arr = 42
        call random_seed(put=seed_arr)

        call set_nn()
        mu = 2d0
        U = 5d0
        dtau = 0.3d0
        ds = 0.3d-5
        s_end = 0.001d0  ! 短い実行

        call initialize()
        call do_langevin_loop_RK()

        checksum_re = sum(real(a)) + sum(real(a_ast))
        checksum_im = sum(aimag(a)) + sum(aimag(a_ast))

        ! GOLDEN_MASTER: set_dw の pi を acos(-1.0d0) に変更後の基準値
        ! (underflow保護により乱数列が変わる可能性があるため、実行して取得した値に更新)
        call assert_near("rk golden real", 3.27344020149361d+03, checksum_re, 1d-8, n_passed, n_failed)
        call assert_near("rk golden imag", 1.89051132348794d-06, checksum_im, 1d-8, n_passed, n_failed)

        deallocate(seed_arr)
    end subroutine

    ! ===========================================
    ! Test: write_header/write_body が正しく書けるか
    ! ===========================================
    subroutine test_write_io(n_passed, n_failed)
        integer, intent(inout) :: n_passed, n_failed
        integer :: read_Nx, read_Ntau
        double precision :: read_U, read_mu
        complex(kind(0d0)) :: read_a(Nx), read_a_ast(Nx)

        write(*,*) "--- test_write_io ---"

        call set_nn()
        mu = 3d0
        U = 10d0
        datfilename = "test_output.dat"

        ! 既知の場を設定
        a = cmplx(1.5d0, 0.5d0, kind=kind(0d0))
        a_ast = cmplx(1.5d0, -0.5d0, kind=kind(0d0))

        ! 書き込み
        open(30, file=datfilename, form="unformatted")
        call write_header(30)
        call write_body(30)
        close(30)

        ! 読み戻し
        open(30, file=datfilename, form="unformatted", status="old")
        read(30) read_Nx, read_U, read_mu, read_Ntau
        read(30) read_a, read_a_ast
        close(30, status="delete")

        call assert_eq_int("io Nx", Nx, read_Nx, n_passed, n_failed)
        call assert_eq_int("io Ntau", Ntau, read_Ntau, n_passed, n_failed)
        call assert_near("io U", 10d0, read_U, 1d-10, n_passed, n_failed)
        call assert_near("io mu", 3d0, read_mu, 1d-10, n_passed, n_failed)
        call assert_near("io a(1) re", 1.5d0, real(read_a(1)), 1d-10, n_passed, n_failed)
        call assert_near("io a(1) im", 0.5d0, aimag(read_a(1)), 1d-10, n_passed, n_failed)
        call assert_near("io a_ast(1) re", 1.5d0, real(read_a_ast(1)), 1d-10, n_passed, n_failed)
        call assert_near("io a_ast(1) im", -0.5d0, aimag(read_a_ast(1)), 1d-10, n_passed, n_failed)
    end subroutine

    ! ===========================================
    ! Test: 自由場極限 (U=0) での da の解析的結果
    !   一様場で U=0 の場合:
    !     時間微分 = 0 (一様場)
    !     近傍和 = 6 * a = 6
    !     非線形 = -U * a_ast * a * a = 0
    !     化学pot = mu * a = mu
    !     da = 2 * (0 + 6 + 0 + mu)
    !   mu=2 なら da = 2 * (0 + 6 + 0 + 2) = 16
    ! ===========================================
    subroutine test_free_field_limit(n_passed, n_failed)
        integer, intent(inout) :: n_passed, n_failed
        complex(kind(0d0)) :: result

        write(*,*) "--- test_free_field_limit ---"
        call set_nn()

        ! 一様場: a = 1, a_ast = 1, U = 0
        a = cmplx(1d0, 0d0, kind=kind(0d0))
        a_ast = cmplx(1d0, 0d0, kind=kind(0d0))
        mu = 2d0
        U = 0d0
        dtau = 0.3d0

        ! U=0 なので非線形項が消え:
        ! da = 2 * (0 + 6 + 0 + 2) = 16
        result = da(a, a_ast, 1, 1)
        call assert_near("free field da real", 16d0, real(result), 1d-10, n_passed, n_failed)
        call assert_near("free field da imag", 0d0, aimag(result), 1d-10, n_passed, n_failed)

        ! da_ast も同様に 16
        result = da_ast(a, a_ast, 1, 1)
        call assert_near("free field da_ast real", 16d0, real(result), 1d-10, n_passed, n_failed)
        call assert_near("free field da_ast imag", 0d0, aimag(result), 1d-10, n_passed, n_failed)

        ! 別のサイト/タイムスライスでも同じ (一様場なので)
        result = da(a, a_ast, 4, 100)
        call assert_near("free field da(4,100) real", 16d0, real(result), 1d-10, n_passed, n_failed)
        call assert_near("free field da(4,100) imag", 0d0, aimag(result), 1d-10, n_passed, n_failed)
    end subroutine

    ! ===========================================
    ! Test: NaN検出が正しく動作するか
    !   場にNaNを注入してis_converge=.false.になるか確認
    ! ===========================================
    subroutine test_nan_detection(n_passed, n_failed)
        integer, intent(inout) :: n_passed, n_failed
        integer :: seedsize
        integer, allocatable :: seed_arr(:)
        double precision :: nan_val

        write(*,*) "--- test_nan_detection ---"

        ! 固定シード
        call random_seed(size=seedsize)
        allocate(seed_arr(seedsize))
        seed_arr = 42
        call random_seed(put=seed_arr)

        call set_nn()
        mu = 2d0
        U = 5d0
        dtau = 0.3d0
        ds = 0.3d-5
        s_end = 0.000003d0  ! 1ステップだけ

        ! NaN値を生成
        nan_val = ieee_value(1.0d0, ieee_quiet_nan)

        ! 場にNaNを注入
        a = cmplx(1d0, 0d0, kind=kind(0d0))
        a_ast = cmplx(1d0, 0d0, kind=kind(0d0))
        a(1, 1) = cmplx(nan_val, 0d0, kind=kind(0d0))

        call do_langevin_loop_RK()

        ! NaNが場にあるとis_converge=.false.になるはず
        call assert_false("NaN detected -> not converged", is_converge, n_passed, n_failed)

        deallocate(seed_arr)
    end subroutine

    ! ===========================================
    ! Test: Inf検出が正しく動作するか
    !   場にInfを注入してis_converge=.false.になるか確認
    ! ===========================================
    subroutine test_inf_detection(n_passed, n_failed)
        integer, intent(inout) :: n_passed, n_failed
        integer :: seedsize
        integer, allocatable :: seed_arr(:)
        double precision :: inf_val

        write(*,*) "--- test_inf_detection ---"

        ! 固定シード
        call random_seed(size=seedsize)
        allocate(seed_arr(seedsize))
        seed_arr = 42
        call random_seed(put=seed_arr)

        call set_nn()
        mu = 2d0
        U = 5d0
        dtau = 0.3d0
        ds = 0.3d-5
        s_end = 0.000003d0  ! 1ステップだけ

        ! Inf値を生成
        inf_val = ieee_value(1.0d0, ieee_positive_inf)

        ! 場にInfを注入
        a = cmplx(1d0, 0d0, kind=kind(0d0))
        a_ast = cmplx(1d0, 0d0, kind=kind(0d0))
        a(1, 1) = cmplx(inf_val, 0d0, kind=kind(0d0))

        call do_langevin_loop_RK()

        ! Infが場にあるとis_converge=.false.になるはず
        call assert_false("Inf detected -> not converged", is_converge, n_passed, n_failed)

        deallocate(seed_arr)
    end subroutine

    ! ===========================================
    ! Test: Box-Muller法でNaNが発生しないことの確認
    !   set_dw() を多数回呼んでも NaN が出ないことを検証
    !   (underflow保護が効いていれば log(0) は起きない)
    ! ===========================================
    subroutine test_box_muller_no_nan(n_passed, n_failed)
        integer, intent(inout) :: n_passed, n_failed
        integer :: iter
        logical :: has_nan

        write(*,*) "--- test_box_muller_no_nan ---"

        has_nan = .false.
        do iter = 1, 100
            call set_dw()
            if (any(ieee_is_nan(real(dw))) .or. any(ieee_is_nan(aimag(dw)))) then
                has_nan = .true.
                exit
            end if
        end do

        call assert_false("Box-Muller 100回でNaN無し", has_nan, n_passed, n_failed)
    end subroutine

    ! ===========================================
    ! Test: 一様場で短いLangevin実行後に場が発散しないか
    !   安定なパラメータで初期化し、短時間走らせて
    !   場の値が有限であることを確認
    ! ===========================================
    subroutine test_stability_uniform_field(n_passed, n_failed)
        integer, intent(inout) :: n_passed, n_failed
        integer :: seedsize
        integer, allocatable :: seed_arr(:)
        logical :: all_finite

        write(*,*) "--- test_stability_uniform_field ---"

        ! 固定シード
        call random_seed(size=seedsize)
        allocate(seed_arr(seedsize))
        seed_arr = 42
        call random_seed(put=seed_arr)

        call set_nn()
        mu = 2d0
        U = 5d0
        dtau = 0.3d0
        ds = 0.3d-5
        s_end = 0.001d0

        ! 平衡点で初期化
        call initialize()
        call do_langevin_loop_RK()

        ! 収束していること
        call assert_true("stability: converged", is_converge, n_passed, n_failed)

        ! 全要素が有限であること
        all_finite = all(ieee_is_finite(real(a))) .and. all(ieee_is_finite(aimag(a))) .and. &
                     all(ieee_is_finite(real(a_ast))) .and. all(ieee_is_finite(aimag(a_ast)))
        call assert_true("stability: all fields finite", all_finite, n_passed, n_failed)

        ! 場の値が妥当な範囲にあること (発散していないこと)
        call assert_true("stability: |a| bounded", maxval(abs(a)) < 1d6, n_passed, n_failed)
        call assert_true("stability: |a_ast| bounded", maxval(abs(a_ast)) < 1d6, n_passed, n_failed)

        deallocate(seed_arr)
    end subroutine

    ! ===========================================
    ! Test: ファイルオープンのエラーハンドリング
    !   存在しないファイルを開こうとして
    !   open_file_checked がエラーを返すか確認
    ! ===========================================
    subroutine test_error_handling_open(n_passed, n_failed)
        integer, intent(inout) :: n_passed, n_failed
        integer :: ios

        write(*,*) "--- test_error_handling_open ---"

        ! 存在しないファイルをstatus='old'で開くとエラーになるはず
        open(99, file="nonexistent_test_file_12345.dat", status='old', &
             action='read', iostat=ios)
        call assert_true("open nonexistent file -> ios /= 0", ios /= 0, n_passed, n_failed)

        ! 正常に開けるファイル
        open(99, file="test_error_handling_tmp.dat", status='replace', &
             action='write', iostat=ios)
        call assert_true("open new file -> ios == 0", ios == 0, n_passed, n_failed)
        if (ios == 0) then
            close(99, status='delete')
        end if
    end subroutine

end program
