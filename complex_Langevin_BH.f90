module functions_module
    implicit none

    logical :: is_converge

    integer, parameter :: Ntau = 6, Nx = 6, Ny = 6, Nz = 6, Dx = Nx*Ny*Nz
    integer, protected :: nn(6, Dx), idxtopos(3, Dx), postoidx(Nx, Ny, Nz)
    double precision :: mu, U, dtau, ds, s_end

    character(len=100) :: datfilename

    namelist /params/ mu, U, dtau, ds, s_end, datfilename

    complex(kind(0d0)) :: a(Ntau, Dx), a_ast(Ntau, Dx)
    complex(kind(0d0)), protected :: dw(Ntau, Dx)
contains
    double precision function random_normal() ! using Box-Muller transform, return a sample from normal dist. (mean = 0, variance = 1).
        double precision :: X, Y
        double precision, parameter :: pi = 3.1415926535897932384626433832795028841971693d0
        call random_number(X)
        call random_number(Y)
        random_normal = sqrt(-2.0d0 * log(X)) * cos(2.0d0 * PI * Y)
    end function

    subroutine make_pos_arrays()
        integer :: x, y, z, i
        i = 1
        do x = 1, Nx
            do y = 1, Ny
                do z = 1, Nz
                    idxtopos(1, i) = x
                    idxtopos(2, i) = y
                    idxtopos(3, i) = z
                    postoidx(x, y, z) = i
                    i = i + 1
                end do
            end do
        end do
    end subroutine

    logical function is_neighbor_pbc(x, xx, period)!
        integer :: x, xx, period
        is_neighbor_pbc = (modulo(x+1, period) == modulo(xx, period)) .or. (modulo(x-1, period) == modulo(xx, period))
    end function

    subroutine set_nn()
        integer :: i, j, x, y, z, xx, yy, zz, c
        logical :: is_neighbor

        nn = -1

        call make_pos_arrays()
        do i = 1, Dx
            x = idxtopos(1, i)
            y = idxtopos(2, i)
            z = idxtopos(3, i)

            c = 1
            do j = 1, Dx
                xx = idxtopos(1, j)
                yy = idxtopos(2, j)
                zz = idxtopos(3, j)
                is_neighbor = ( is_neighbor_pbc(x, xx, Nx) .and. y - yy == 0 .and. z - zz == 0 )
                is_neighbor = is_neighbor .or. ( x - xx == 0 .and. is_neighbor_pbc(y, yy, Ny) .and. z - zz == 0 )
                is_neighbor = is_neighbor .or. ( x - xx == 0 .and. y - yy == 0 .and. is_neighbor_pbc(z, zz, Nz) )
                if (is_neighbor) then
                    nn(c, i) = j
                    c = c + 1
                end if
            end do
        end do
    end subroutine

    complex(kind(0d0)) function da(a, a_ast, tau, x)! a, a_astからdaを計算
        integer :: tau, x, y, i
        complex(kind(0d0)), intent(in) :: a(:,:), a_ast(:,:)

        da = a(modulo(tau, Ntau)+1, x)
        if ((tau-1) == 0) then ! tauが周期的なのでその処理
            da = da - a(Ntau, x)
        else
            da = da - a(tau-1, x)
        end if
        da = da / (2d0 * dtau)
        do i = 1, 6
            y = nn(i, x)
            if (y > 0) then
                da = da + a(tau, y)
            end if
        end do
        da = da - U * a_ast(tau, x) * a(tau, x) * a(tau, x)
        da = da + mu * a(tau, x)
        da = 2d0 * da
    end function

    complex(kind(0d0)) function da_ast(a, a_ast, tau, x)!da_astを計算
        integer :: tau, x, y, i
        complex(kind(0d0)), intent(in) :: a(:,:), a_ast(:,:)

        da_ast = a_ast(modulo(tau, Ntau)+1, x)
        if ((tau-1) == 0) then!tauが周期的なのでその処理
            da_ast = da_ast - a_ast(Ntau, x)
        else
            da_ast = da_ast - a_ast(tau-1, x)
        end if
        da_ast = -da_ast / (2d0 * dtau)
        do i = 1, 6
            y = nn(i, x)
            if (y > 0) then
                da_ast = da_ast + a_ast(tau, y)
            end if
        end do
        da_ast = da_ast - U * a_ast(tau, x) * a_ast(tau, x) * a(tau, x)
        da_ast = da_ast + mu * a_ast(tau, x)
        da_ast = 2d0 * da_ast
    end function

    subroutine set_dw()!dwにガウシアンノイズを代入
        integer :: i, j
        do j = 1, Dx
            do i = 1, Ntau
                dw(i, j) = complex(random_normal(), random_normal())
            end do
        end do
    end subroutine

    subroutine initialize()
        double precision :: y
        y = sqrt((6d0 + mu) / U)
        a = complex(y, 0d0)
        a_ast = complex(y, 0d0)
    end subroutine

    subroutine do_langevin_loop_RK()! Langevin方程式を解く部分
        complex(kind(0d0)) :: a_mid(Ntau, Dx), a_ast_mid(Ntau, Dx), a_next(Ntau, Dx), a_ast_next(Ntau, Dx)
        double precision :: s, sigma
        integer :: x, tau
        sigma = sqrt(2d0 * ds / dtau)

        s = 0d0
        is_converge = .true.
        do while (s < s_end)
            s = s + ds
            call set_dw()
            do x = 1, Dx
                do tau = 1, Ntau
                    a_mid(tau, x) = a(tau, x) + da(a, a_ast, tau, x) * ds + sigma * dw(tau, x)
                    a_ast_mid(tau, x) = a_ast(tau, x) + da_ast(a, a_ast, tau, x) * ds + sigma * conjg(dw(tau, x))
                end do
            end do
            do x = 1, Dx
                do tau = 1, Ntau
                    a_next(tau, x) = a(tau, x) + &
                        0.5d0 * (da(a, a_ast, tau, x) + da(a_mid, a_ast_mid, tau, x)) * ds + sigma * dw(tau, x)
                    a_ast_next(tau, x) = a_ast(tau, x) + &
                        0.5d0 * (da_ast(a, a_ast, tau, x) + da_ast(a_mid, a_ast_mid, tau, x)) * ds + sigma * conjg(dw(tau, x))
                    if ( isnan(real(a_next(tau, x))) .or. isnan(imag(a_next(tau, x))) ) then
                        is_converge = .false.
                        return
                    endif
                end do
            end do
            a = a_next
            a_ast = a_ast_next
        end do
    end subroutine

    subroutine write_header()
        open(20, file=datfilename, form="unformatted")
        write(20) Nx, U, mu, Ntau
        close(20)
    end subroutine

    subroutine write_body()
        complex(kind(0d0)) :: arr1(Nx), arr2(Nx)
        integer :: i
        open(20, file=datfilename, form="unformatted", position='append')
        !write(20) Nx, U, mu
        do i = 1, Nx
            arr1(i) = a(1, i)
            arr2(i) = a_ast(1, i)
        end do
        write(20) arr1, arr2
        close(20)
    end subroutine
end module

program complex_Langevin_BH
    use functions_module
    implicit none
    
    integer :: i, Nsample, Nfailed
    character(len=60) :: arg

    namelist /sampling_setting/ Nsample

    ! 乱数シードをシステムのエントロピーから初期化
    ! (並列実行時に各プロセスが異なる乱数列を使う)
    ! 再現性が必要な場合は call random_seed(put=...) で固定値を設定する
    call random_seed()

    ! set_nn() の呼び出し
    ! idx, (x, y, z)の変換を行うための配列が定義される
    call set_nn()

    ! 実行時引数の読み取り
    call get_command_argument(1, arg)
    if (len_trim(arg) == 0) then
        stop "parameter file is required."
    end if
    
    ! 実行時引数で与えられた(params.dat)を開く
    open(11, file=trim(arg), status='old', action='read')
    ! (params.datの)&params部分を読み込む
    read(11, nml=params)
    ! &sampling_setting部分を読み込む
    read(11, nml=sampling_setting)
    close(11)

    write(*, *) "mu, U, dtau, Ntau, ds, s_end, Nsample = ", mu, U, dtau, Ntau, ds, s_end, Nsample

    Nfailed = 0
    call write_header()
    do i = 1, Nsample
        call initialize()
        write(*, *) "sample: ", i, " / ", Nsample, Nfailed
        call do_langevin_loop_RK()
        if (is_converge) then
            call write_body()
        else
            Nfailed = Nfailed + 1
        end if
    end do
end program
