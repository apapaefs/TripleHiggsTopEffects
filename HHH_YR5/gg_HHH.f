!
!  SPDX-License-Identifier: GPL-3.0-or-later
!  Copyright (C) 2019-2022, respective authors of MCFM.
!
      subroutine gg_HHH(p,msq)
      implicit none
      include 'types.f'
c-----Matrix element squared for triple Higgs production
c-----g(-p1)+g(-p2) --> H(p3,p4)+H(p5,p6)+H(p7,p8)

      include 'constants.f'
      include 'nf.f'
      include 'mxpart.f'
      include 'masses.f'
      include 'qcdcouple.f'
      include 'hdecaymode.f'
      include 'ewcouple.f'
      include 'mh.f'
      include 'blha.f'
! UH 24/1/26: added 
      include 'anomHiggs.f'
      integer:: j,h1,h2
! UH 24/1/26: extended ampsq
      real(dp):: msq(-nf:nf,-nf:nf),p(mxpart,4),fac,ampsq(0:9)
      complex(dp):: fullamp(2,2),amp(2,2),amp3H(2,2),amp4Ha(2,2),amp4Hb(2,2)
      complex(dp):: fullamp_b(2,2),amp_b(2,2),amp3H_b(2,2),amp4Ha_b(2,2),amp4Hb_b(2,2)
! labels for components of matrix element squared
! UH 24/1/26: added ktSM 
      integer ::  k4=1, k4sq=2, k3=3, k3k4=4, k3sq=5, k3sqk4=6, k3cu=7, k3qu=8, ktSM = 9
      common/HHHampsqbits/ampsq
!$omp threadprivate(/HHHampsqbits/)

      msq(:,:)=zip

! fill common block used in HHH routines
      mhsq=hmass**2
      mtsq=mt**2
      call ampHHH(p,fullamp,amp,amp3H,amp4Ha,amp4Hb)
      fullamp=mt**4*fullamp
      amp=mt**4*amp
      amp3H=mt**4*amp3H
      amp4Ha=mt**4*amp4Ha
      amp4Hb=mt**4*amp4Hb
! retain the dependence on the bottom quark mass if it's non-zero
      if (mb < 1.e-5_dp) then
        fullamp_b=0;amp_b=0;amp3H_b=0;amp4Ha_b=0;amp4Hb_b=0
      else
        mtsq=mb**2
        call ampHHH(p,fullamp_b,amp_b,amp3H_b,amp4Ha_b,amp4Hb_b)
        fullamp=fullamp+mb**4*fullamp_b
        amp=amp+mb**4*amp_b
        amp3H=amp3H+mb**4*amp3H_b
        amp4Ha=amp4Ha+mb**4*amp4Ha_b
        amp4Hb=amp4Hb+mb**4*amp4Hb_b
      endif

! UH 24/1/26: added

      kt=cttH
      ktsq=kt**2

!     write(6,*) 'kt',kt

      ampsq=zip
      do h1=1,2
      do h2=1,2
      ampsq(0)=ampsq(0)+abs(fullamp(h1,h2))**2
! decomposition of amplitude, see decomp.frm
!       + dk4 * ( 2*amp4Ha*amp4Hb + 2*amp4Ha^2 + 2*amp3H*amp4Ha + 2*amp*amp4Ha )
!       + dk4^2 * ( amp4Ha^2 )
!       + dk3 * ( 4*amp4Hb^2 + 4*amp4Ha*amp4Hb + 6*amp3H*amp4Hb + 2*amp3H*amp4Ha + 2*amp3H^2 + 4*amp*amp4Hb + 2*amp*amp3H )
!       + dk3*dk4 * ( 4*amp4Ha*amp4Hb + 2*amp3H*amp4Ha )
!       + dk3^2 * ( 6*amp4Hb^2 + 2*amp4Ha*amp4Hb + 6*amp3H*amp4Hb + amp3H^2 + 2*amp*amp4Hb )
!       + dk3^2*dk4 * ( 2*amp4Ha*amp4Hb )
!       + dk3^3 * ( 4*amp4Hb^2 + 2*amp3H*amp4Hb )
!       + dk3^4 * ( amp4Hb^2 )

!      ampsq(k4)=ampsq(k4)+2*real(conjg(amp4Ha(h1,h2))*
!     & (amp(h1,h2)+amp3H(h1,h2)+amp4Ha(h1,h2)+amp4Hb(h1,h2)))

! UH 24/1/26: added kt dependence
      
      ampsq(k4)=ampsq(k4)+2*ktsq*real(conjg(amp4Ha(h1,h2))*
     & (ktsq*amp(h1,h2)+kt*amp3H(h1,h2)+amp4Ha(h1,h2)+amp4Hb(h1,h2)))
    
!      ampsq(k4sq)=ampsq(k4sq)+abs(amp4Ha(h1,h2))**2

! UH 24/1/26: added kt dependence

      ampsq(k4sq)=ampsq(k4sq)+ktsq*abs(amp4Ha(h1,h2))**2

!      ampsq(k3)=ampsq(k3)+2*real(conjg(amp3H(h1,h2))*
!     & (amp(h1,h2)+amp3H(h1,h2)+amp4Ha(h1,h2)+3*amp4Hb(h1,h2))
!     & +2*conjg(amp4Hb(h1,h2))*(amp(h1,h2)+amp4Ha(h1,h2)+amp4Hb(h1,h2)))

! UH 24/1/26: added kt dependence

      ampsq(k3)=ampsq(k3)+2*ktsq*real(kt*conjg(amp3H(h1,h2))*
     & (ktsq*amp(h1,h2)+kt*amp3H(h1,h2)+amp4Ha(h1,h2)+3*amp4Hb(h1,h2))
     & +2*conjg(amp4Hb(h1,h2))*(ktsq*amp(h1,h2)+amp4Ha(h1,h2)+amp4Hb(h1,h2)))           

!      ampsq(k3k4)=ampsq(k3k4)+2*real(conjg(amp4Ha(h1,h2))*
!     & (amp3H(h1,h2)+2*amp4Hb(h1,h2)))

! UH 24/1/26: added kt dependence

      ampsq(k3k4)=ampsq(k3k4)+2*ktsq*real(conjg(amp4Ha(h1,h2))*
     & (kt*amp3H(h1,h2)+2*amp4Hb(h1,h2)))
    
!      ampsq(k3sq)=ampsq(k3sq)+abs(amp3H(h1,h2))**2
!     & +2*real(conjg(amp4Hb(h1,h2))*(amp(h1,h2)+amp4Ha(h1,h2))
!     &      +3*conjg(amp4Hb(h1,h2))*(amp3H(h1,h2)+amp4Hb(h1,h2)))

! UH 24/1/26: added kt dependence

      ampsq(k3sq)=ampsq(k3sq)+ ktsq*(ktsq*abs(amp3H(h1,h2))**2
     & +2*real(conjg(amp4Hb(h1,h2))*(ktsq*amp(h1,h2)+amp4Ha(h1,h2))
     &      +3*conjg(amp4Hb(h1,h2))*(kt*amp3H(h1,h2)+amp4Hb(h1,h2))))         

!      ampsq(k3sqk4)=ampsq(k3sqk4)+2*real(conjg(amp4Ha(h1,h2))*amp4Hb(h1,h2))

! UH 24/1/26: added kt dependence

      ampsq(k3sqk4)=ampsq(k3sqk4)+2*ktsq*real(conjg(amp4Ha(h1,h2))*amp4Hb(h1,h2))
      
!      ampsq(k3cu)=ampsq(k3cu)+2*real(conjg(amp4Hb(h1,h2))*
!     & (amp3H(h1,h2)+2*amp4Hb(h1,h2)))

! UH 24/1/26: added kt dependence

      ampsq(k3cu)=ampsq(k3cu)+2*ktsq*real(conjg(amp4Hb(h1,h2))*
     & (kt*amp3H(h1,h2)+2*amp4Hb(h1,h2)))

!      ampsq(k3qu)=ampsq(k3qu)+abs(amp4Hb(h1,h2))**2

! UH 24/1/26: added kt dependence

      ampsq(k3qu)=ampsq(k3qu)+ktsq*abs(amp4Hb(h1,h2))**2

! UH 24/1/26: added

      ampsq(ktSM)=ampsq(ktSM)
     & +ktsq*abs(ktsq*amp(h1,h2)+kt*amp3H(h1,h2)+amp4Ha(h1,h2)+amp4Hb(h1,h2))**2
     & -abs(fullamp(h1,h2))**2  

      enddo
      enddo
      
! overall factors, including 1/6 for symmetry and delta(AB)^2=V
      fac=V/6._dp*(gsq/(16*pisq))**2/vevsq**3
      
      msq(0,0)=avegg*fac*ampsq(0)
      
      return
      end
