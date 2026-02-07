program test_functions
    use functions_module
    implicit none

    integer :: n_passed, n_failed
    n_passed = 0
    n_failed = 0

    call test_set_nn(n_passed, n_failed)
    call test_da_uniform(n_passed, n_failed)
    call test_da_ast_uniform(n_passed, n_failed)
    call test_rk_golden_master(n_passed, n_failed)
    call test_write_io(n_passed, n_failed)

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
        a = complex(1d0, 0d0)
        a_ast = complex(1d0, 0d0)
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

        a = complex(1d0, 0d0)
        a_ast = complex(1d0, 0d0)
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

        ! GOLDEN_MASTER: Box-Muller最適化後の基準値
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
        a = complex(1.5d0, 0.5d0)
        a_ast = complex(1.5d0, -0.5d0)

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

end program
