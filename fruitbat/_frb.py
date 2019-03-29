"""
Frb class and method functions.
"""
from __future__ import print_function, absolute_import, division

from e13tools import docstring_substitute

import numpy as np
import astropy.coordinates as coord
from astropy.coordinates import SkyCoord
from astropy.time import Time
import astropy.units as u

import pyymw16 as ymw16

from fruitbat import estimate, cosmology

__all__ = ["Frb"]

class Frb(object):
    """
    Create a :class:`~Frb` object using the observered properties of a FRB
    including dispersion measure (DM) and its sky coordinates. This class
    utilises various DM-redshift relations as well as the YMW16 galactic DM
    model in the analysis.

    A FRB can be defined simply with a single :attr:`dm` value. This should be
    the observed DM prior to subtracting the Milky Way, however if you do not
    provide any additional information, it is asssumed that this value is also
    the :attr:`dm_excess` (DM - Galactic DM). You can get the estimated
    redshift by using the method :meth:`calc_redshift`.

    To get a more accurate distance estimate you can account for
    the contribution due to the Milky Way by supplying :attr:`dm_galaxy` or by
    giving the coordinates of the FRB in ICRS (:attr:`raj`, :attr:`decj`) or
    Galactic (:attr:`gl`, :attr:`gb`) coordinates and calling the method
    :meth:`calc_dm_galaxy` before calling :meth:`calc_redshift`.


    Parameters
    ----------
    dm : float
        The observed dispersion measure of the FRB. This is without Milky Way
        or host galaxy subtraction.
        Units: pc cm**-3

    Keyword Arguments
    -----------------
    name : str or None, optional
        The name of the frb object. Default: *None*

    raj : str or None, optional
        The right ascension in J2000 coordinates of the best estimate of the
        FRB position. Default: *None*

    decj : str or None, optional
        The declination in J2000 coordinates of the best estimate of the
        FRB position. Default: *None*

    gl : str or None, optional
        The Galactic longitude in degrees of the best estimate of the FRB
        position. Default: *None*

    gb : str or None, optional
        The Galactic latitude in degrees of the best estimate of the FRB
        position. Default: *None*

    Other Parameters
    ----------------
    dm_galaxy : float, optional
        The modelled contribution to the FRB DM by electrons in the Milky Way.
        This value is calculated using :meth:`calc_dm_galaxy`
        Units: pc cm**-3 Default: 0.0

    dm_excess : float or None, optional
        The DM excess of the FRB over the estimated Galactic DM. If
        :attr:`dm_excess` is *None*, then :attr:`dm_excess` is calculated
        automatically with :meth:`calc_dm_excess`.
        Units: pc cm**-3 Default: *None*

    z_host : float or None, optional
        The observed redshift of the localised FRB host galaxy.
        Default: *None*

    dm_host_est : float, optional
        The estimated contribution to the measured FRB DM from originating from
        the FRB's host galaxy. This value is the amount of DM the host galaxy
        contributes to the observed DM, *not* the DM of the host galaxy.
        Setting this to a non-zero value and setting ``subtract_host=True``
        when calling :meth:`calc_redshift` accounts for the DM contribution
        due to the host galaxy. Units: pc cm**-3 Default: 0.0

    dm_host_loc : float, optional
        The dispersion measure of a localised FRB host galaxy. This value is
        *not* the contribution to the observed DM, but the DM at the host
        galaxy. The observed DM is :attr:`dm_host_loc` but attenuated by a
        factor of (1 + z). To use this, the redshift of the host galaxy must
        be known. Units: pc cm**-3 Default: 0.0

    dm_index : float or None, optional
        The dispersion measure index of the burst :math:`\\alpha` such that
        :math:`\\rm{DM} \\propto \\nu^{-\\alpha}` Default: *None*

    scatt_index : float or None, optional
        The scattering index (:math:`\\beta`) of the FRB pulse. The
        scattering index describes how the width (:math:`\\rm{W}`) of the
        FRB pulse evolves with frequency :math:`\\nu` such that
        :math:`\\rm{W} \\propto \\nu^{-\\beta}`. Default: *None*

    snr : float or None, optional
        The signal-to-noise of the burst.
        Default: *None*

    width : float or None, optional
        The observed width of the pulse obtained by a pulse fitting algorithm.
        Units: ms Default: *None*

    peak_flux : float or None, optional
        The observed peak flux density of the burst.
        Units: Jy Default: *None*

    fluence : float or None, optional
        The observed fluence of the FRB. If :attr:`fluence` is *None* and both
        :attr:`width` and :attr:`peak_flux` are not *None* then :attr:`fluence`
        is automatically calculated with :meth:`calc_fluence`
        Units: Jy ms Default: *None*

    obs_bandwidth : float or None, optional
        The observing bandwidth. Units: MHz Default: *None*

    utc : str or None, optional
        The UTC time of the FRB Burst. Format should be of the form
        '1999-01-01T00:00:00.000'. Default: *None*


    Example
    -------
    >>> import fruitbat
    >>> FRB = fruitbat.Frb(879, gl="12:31:40.5", gb="3:41:10.0")
    >>> FRB.calc_dm_galaxy()
    >>> FRB.calc_redshift()

    """

    def __init__(self, dm, name=None, raj=None, decj=None, gl=None, gb=None, 
                 dm_galaxy=0.0, dm_excess=None, z_host=None, dm_host_est=0.0, 
                 dm_host_loc=0.0, dm_index=None, scatt_index=None, snr=None,
                 width=None, peak_flux=None, fluence=None, obs_bandwidth=None,
                 utc=None, *args, **kwargs):

        self.name = name
        self.dm = dm
        self.dm_galaxy = dm_galaxy
        self.dm_host_est = dm_host_est
        self.dm_host_loc = dm_host_loc

        # Calculate dm_excess from existing parameters if it is not given.
        if dm_excess is None:
            self.calc_dm_excess()
        else:
            self.dm_excess = dm_excess

        self.dm_index = dm_index
        self.z_host = z_host
        self.scatt_index = scatt_index
        self.snr = snr
        self.width = width
        self.peak_flux = peak_flux
        self.obs_bandwidth = obs_bandwidth
        self.utc = utc
        self.raj = raj
        self.decj = decj
        self.gl = gl
        self.gb = gb
        self.fluence = fluence

        self.z = None
        self.dm_igm = None
        self.cosmology_method = None

        # Calculate fluence if peak_flux and width are given
        if (self.fluence is None) and (peak_flux is not None and width is not None):
            self.calc_fluence()

        # Calculate the skycoords of the FRB from (raj, decj) or (gl, gb)
        if (raj and decj) or (gl and gb):
            self.skycoords = self.calc_skycoords()
            self.raj = self.skycoords.icrs.ra
            self.decj = self.skycoords.icrs.dec
            self.gl = self.skycoords.galactic.l
            self.gb = self.skycoords.galactic.b
        else:
            self.skycoords = None

    def __repr__(self):
        return 'Frb({})'.format(vars(self))

    @docstring_substitute(methods=estimate.methods(string=True),
                          cosmo=cosmology.keys())
    def calc_redshift(self, method='Inoue2004', cosmology="Planck18",
                      subtract_host=False):
        """
        Calculate the redshift of the FRB from its :attr:`dm`,
        :attr:`dm_excess` or :attr:`dm_excess` - :attr:`dm_host_est`.

        Parameters
        ----------
        method : str, optional
            The approximation to use when calculating the redshift.
            Avaliable methods:  %(methods)s. Default: Inoue2004

        cosmology : str, optional
            The method `inoue2004` has the option to choose which cosmology
            to assume when performing the redshift estimation.
            Avaliable cosmologies: %(cosmo)s. Default: Planck18

        subtract_host : bool, optional
            Subtract :attr:`dm_host_est` from the :attr:`dm_excess` before
            calculating the redshift. This is is used to account for the
            dispersion measure that arises from the FRB host galaxy. 
            Default: False

        Returns
        -------
        float
            The redshift of the FRB.

        Notes
        -----
        The methods_ section in the documentation has a discription of each
        methods and where they should apply.

        The cosmology_ section of the documentation has a list of the
        cosmological parameters used in each cosmology method.

        .. _cosmology: https://fruitbat.readthedocs.io/en/latest/user_guide/method_and_cosmology.html#cosmology
        .. _methods: https://fruitbat.readthedocs.io/en/latest/user_guide/method_and_cosmology.html#methods
        """
        if not isinstance(subtract_host, bool):
            raise ValueError("subtract_host must be of type bool.")

        if subtract_host:
            input_dm = self.dm_excess - self.dm_host_est
        else:
            input_dm = self.dm_excess

        self.z = estimate.redshift(input_dm, method=method,
                                   cosmology=cosmology)

        self.cosmology_method = cosmology
        return self.z

    def calc_skycoords(self):
        """
        Calculates the skycoord position on the sky of the FRB from
        (:attr:`raj`, :attr:`decj`) or (:attr:`gl`, :attr:`gb`).

        Returns
        -------
        :obj:`astropy.coordinates.SkyCoord`
            The sky coordinates of the FRB.
        """

        if self.raj is not None and self.decj is not None:
            skycoords = SkyCoord(self.raj, self.decj, frame="icrs",
                                 unit=(u.hourangle, u.deg))

        elif self.gl is not None and self.gb is not None:
            skycoords = SkyCoord(self.gl, self.gb, frame="galactic",
                                 unit=u.deg)
        else:
            raise ValueError("To calculate skycoords either (raj and decj)"
                             "or (gl, gb) must be provided")

        return skycoords

    def calc_dm_excess(self):
        """
        Calculates the dispersion measure excess of the FRB by subtracting
        the DM contribution from the Milky Way.

        Returns
        -------
        :obj:`astropy.units.Quantity`
            The dispersion measure excess.

        Notes
        -----
        :math:`\\rm{DM_{excess}}` is calculated as follows:

        .. math::

            \\rm{DM_{excess} = DM - DM_{galaxy}}
        """
        dm_excess = self.dm.value - self.dm_galaxy.value
        self.dm_excess = dm_excess
        return dm_excess

    def calc_dm_galaxy(self, model='ymw16'):
        """
        Calculates the dispersion measure contribution of the Milky Way from
        either (:attr:`raj`, :attr:`decj`) or (:attr:`gl`, :attr:`gb`). Uses
        the YMW16 model of the Milky Way electron column density.

        Parameters
        ----------
        model : str, optional
            The Milky Way dispersion measure model. Currently the only
            implemented model is the YMW16 model.

        Returns
        -------
        :obj:`astropy.units.Quantity`
            The dispersion measure contribution from the Milky Way of the FRB.
        """

        # Since the YMW16 model only gives you a dispersion measure out to a
        # distance within the galaxy, to get the entire DM contribution of the
        # galaxy we need to specify the furthest distance in the YMW16 model.
        max_galaxy_dist = 25000  # units: pc

        # Check to make sure some of the keyword are not None
        coord_list = [self.skycoords, self.raj, self.decj, self.gl, self.gb]
        if all(val is None for val in coord_list):
            raise ValueError("""Can not calculate dm_galaxy since coordinates
                             for FRB burst were not provided. Please provide
                             (raj, decj) or (gl, gb) coordinates.""")

        # Calculate skycoords position if it
        elif (self.skycoords is None and
                (self.raj is not None and self.decj is not None) or
                (self.gl is not None and self.gb is not None)):

            self._skycoords = self.calc_skycoords()

        dm_galaxy, tau_sc = ymw16.dist_to_dm(self._skycoords.galactic.l,
                                             self._skycoords.galactic.b,
                                             max_galaxy_dist)

        self.tau_sc = tau_sc
        self.dm_galaxy = dm_galaxy.value
        self.calc_dm_excess()
        return self.dm_galaxy

    def calc_dm_igm(self):
        """
        Calculates the dispersion measure of the intergalactic medium along the
        line-of-sight of the FRB. This can only be done if the redshift and
        dispersion measure contribution of the FRB host galaxy is known.

        Returns
        -------
        :obj:`astropy.units.Quantity`
            The dispersion measure contribution of the IGM.

        Notes
        -----
        :math:`\\rm{DM_{IGM}}` is calculated as follows:

        .. math::

           \\rm{DM_{IGM}} = \\rm{DM_{excess}} - \\frac{\\rm{DM_{host, loc}}}{1 + z}
        """

        if self.z_host is None:
            err_msg = ("z_host is None. Provide a non zero value for the "
                       "FRB host redshift")
            raise ValueError(err_msg)

        if self.dm_host_loc == 0.0:
            err_msg = ("dm_host_loc = 0. The dm_igm will be the same as "
                       "dm_excess. Provide a non-zero value for dm_host_loc")
            raise ValueError(err_msg)

        dm_igm = self.dm_excess - (self.dm_host_loc / (1 + self.z_host))
        self.dm_igm = dm_igm.value
        return self.dm_igm

    def calc_fluence(self):
        """
        Calculates the observed fluence of the FRB. This requires :attr:`width`
        and :attr:`peak_flux` to not be *None*.

        Returns
        -------
        :obj:`astropy.units.Quantity` or None:
            The fluence of the FRB.

        Notes
        -----
        The fluence (:math:`\\rm{F_{obs}}`) is calculated as follows:

        .. math::

            \\rm{F_{obs} = W_{obs} S_{peak, obs}}
        """


        if (self.width is None) or (self.peak_flux is None):
            err_msg = ("calc_fluence requires both width and peak_flux "
                       "to not be None")
            raise ValueError(err_msg)

        fluence = self.width * self.peak_flux
        self.fluence = fluence.value
        return fluence

    def calc_luminosity_distance(self):
        """
        Calculates the luminosity distance to the FRB based on its
        redshift. To calculate a luminosity distance either call
        :meth:`calc_redshift` first to determine a redshift estimate
        or provide a value for :attr:`dm_host`.

        Returns
        -------
        :obj:`astropy.units.Quantity`
            The luminosity distance to the FRB.
        """

        if self.z is None:
            raise ValueError(
                """ Can not calculate luminosity distance without a redshift.
                Use calc_redshift() to calculate the FRB redshift or provide
                a value for z_host.
                """)

        cosmo = cosmology.builtin()[self.cosmology_method]
        return cosmo.luminosity_distance(self.z)

    def calc_comoving_distance(self):
        """
        Calculates the comoving distance to the FRB based on its
        redshift. To calculate a comoving distance either call
        :meth:`calc_redshift` first to determine a redshift estimate
        or provide a value for :attr:`dm_host`.

        Returns
        -------
        :obj:`astropy.units.Quantity`
            The comoving distance to the FRB.
        """
        if self.z is not None:
            z_sample = self.z
        elif self.z_host is not None:
            z_sample = self.z_host
        else:
            raise ValueError(
                """ Can not calculate comoving distance without a redshift.
                Use calc_redshift() to calculate the FRB redshift or provide
                a value for z_host.
                """)

        cosmo = cosmology.builtin()[self.cosmology_method]
        return cosmo.comoving_distance(z_sample)

#    Currently peak luminosity is removed since it's unclear from literature 
#    how to accuratly calculate this quantity
#    def calc_peak_luminosity(self):
#        """
#        Returns
#        -------
#        :obj:`astropy.units.Quantity`
#            The estimated isotropic peak luminosity of the FRB within an
#            observed bandwidth.
#        """
#
#        D = self.calc_luminosity_distance()
#        S = self.peak_flux
#        B = self.obs_bandwidth
#
#        Lum  = 4 * np.pi * D**2 * S * B
#        return lum.to('erg s**-1')


    def calc_energy(self):
        """
        Calculates the isotropic energy of the FRB within an observed
        bandwidth. This is the upper limit to the the true energy since
        the luminosity distance required is also an upper limit to the
        true luminosity distance.

        Returns
        -------
        :obj:`astropy.units.Quantity`
            The estimated isotropic energy of the FRB within the
            observed bandwidth.

        Notes
        -----
        The energy of a FRB is calculated following that in Law et al. 2017
        with the redshift dependence that is included by Zhang 2018.

        .. math::

            E_{FRB} \\simeq F_{obs} B \\frac{4 \\pi D_{\\rm{L}}^2}{1 + z}

        Where :math:`F_{obs}` is the fluence of the FRB, :math:`B` is the
        observing bandwidth, :math:`D_{\\rm{L}}` is the luminosity distance and
        :math:`z` is the estimated redshift.
        """

        D = self.calc_luminosity_distance()
        if self.fluence is None:
            raise ValueError(
                """Can not calculate energy without fluence. Provide fluence or
                peak_flux and width before calculating energy.""")
        else:
            F = self.fluence

        if self.obs_bandwidth is None:
            raise ValueError(
                """Can not calculate energy without observing bandwidth.
                Provide obs_bandwidth before calculating energy.""")
        else:
            B = self.obs_bandwidth

        energy = F * B * 4 * np.pi * D**2 * (1 + self.z)**-1
        return energy.to("erg")

    def _set_value_units(self, value, unit=None, non_negative=False):
        """
        Sets the units of a value.

        Parameters
        ----------
        value: float or int
            The input value.

        unit: :obj:`astropy.unit` or None
            The unit to set for ``value``. If ``unit = None`` then ``value``
            will become a dimensionless quantity.

        non_negative: bool, optional
            If the value is negative raise an error. This is used to check
            that certian values that can only be positive and correctly 
            specified. Default: *False*

        Return
        ------
        var : astropy.unit.Quantity or None
            The 
            If ``value=None`` returns Non
        """
        if value is None:
            var = None
        elif non_negative and value < 0.0:
            raise ValueError("Value must be greater than zero.")
        elif unit is None:
            var = value * u.dimensionless_unscaled
        else:
            var = value * unit

        return var

    @property
    def name(self):
        """
        name: str
            The name of the FRB object.
        """
        return self._name

    @name.setter
    def name(self, value):
        if isinstance(value, str):
            self._name = value
        else:
            self._name = str(value)

    @property
    def dm(self):
        """
        :obj:`astropy.units.Quantity` or None:
            The observed dispersion measure of the FRB. This is without
            Milky Way or host galaxy subtraction.
        """
        return self._dm

    @dm.setter
    def dm(self, value):
        self._dm = self._set_value_units(value, unit=u.pc * u.cm**-3,
                                         non_negative=True)


    @property
    def dm_galaxy(self):
        """
        :obj:`astropy.units.Quantity` or None:
            The galactic component of the dispersion measure. This is quantity
            is calculated using :meth:`calc_dm_galaxy`.
        """
        return self._dm_galaxy

    @dm_galaxy.setter
    def dm_galaxy(self, value):
        self._dm_galaxy = self._set_value_units(value, unit=u.pc * u.cm**-3,
                                                non_negative=True)

    @property
    def dm_excess(self):
        """
        :obj:`astropy.units.Quantity` or None:
            The dispersion measure with the Milky Way component subtracted.
            This value approximates the dispersion measure of the intergalatic
            medium by assuming that the host galaxy contributes zero to the
            observed dispersion measure. This quantity is calculated using
            :meth:`calc_dm_excess`.
        """
        return self._dm_excess

    @dm_excess.setter
    def dm_excess(self, value):
            self._dm_excess = self._set_value_units(value, u.pc * u.cm**-3,
                                                    non_negative=True)

    @property
    def dm_host_est(self):
        """
        :obj:`astropy.units.Quantity` or None:
            The estimated dispersion measure from the FRB host galaxy.
        """
        return self._dm_host_est

    @dm_host_est.setter
    def dm_host_est(self, value):
        self._dm_host_est = self._set_value_units(value, u.pc * u.cm**-3,
                                                  non_negative=True)

    @property
    def dm_host_loc(self):
        """
        :obj:`astropy.units.Quantity` or None:
            The dispersion measure from a localised FRB host galaxy.
        """
        return u.Quantity(self._dm_host_loc, u.pc * u.cm**-3)

    @dm_host_loc.setter
    def dm_host_loc(self, value):
        self._dm_host_loc = self._set_value_units(value, u.pc * u.cm**-3,
                                                  non_negative=True)
#    @property
#    def dm_index(self):
#        """
#        float: The dispersion measure index of the burst.
#        """
#        return self._dm_index

    @property
    def z(self):
        """
        :obj:`astropy.units.Quantity` or None:
            The estimated redshift of the burst. By default this assumes that
            the entire :attr:`dm_excess` arrives from the IGM and the host
            galaxy of the FRB and any surrounding material contribute nothing
            to the total DM. This should be taken as an upper limit to the
            bursts true redshift. To provide an estimate of the DM contribution
            due to he host galaxy, set :attr:`dm_host_est` to a non-zero value
            and use ``subract_host=True`` when calling :meth:`calc_redshift()`.
        """
        return self._z

    @z.setter
    def z(self, value):
        self._z = self._set_value_units(value)

    @property
    def z_host(self):
        """
        :obj:`astropy.units.Quantity` or None:
            The redshift of the localised FRB host galaxy. Note that this an
            observed quantity, not the estimated redshift :attr:`z` calculated
            with :meth:`calc_redshift()`.
        """
        return self._z_host

    @z_host.setter
    def z_host(self, value):
        self._z_host = self._set_value_units(value)

#    @property
#    def scatt_index(self):
#        """float: The scattering index of the FRB."""
#        return self._scatt_index

    @property
    def width(self):
        """
        :obj:`astropy.units.Quantity` or None:
            The observed width of the pulse.
        """
        return self._width

    @width.setter
    def width(self, value):
        self._width = self._set_value_units(value, u.ms, non_negative=True)

    @property
    def peak_flux(self):
        """
        :obj:`astropy.units.Quantity` or None:
            The observed peak flux density of the FRB.
        """
        return self._peak_flux

    @peak_flux.setter
    def peak_flux(self, value):
        self._peak_flux = self._set_value_units(value, u.Jy, non_negative=True)

    @property
    def fluence(self):
        """
        :obj:`astropy.units.Quantity` or None:
            The observed fluence of the FRB. This is calculated from
            :meth:`calc_fluence`.
        """
        return self._fluence

    @fluence.setter
    def fluence(self, value):
        self._fluence = self._set_value_units(value, u.Jy * u.ms,
                                              non_negative=True)

    @property
    def obs_bandwidth(self):
        """
        :obj:`astropy.units.Quantity` or None:
            The observing bandwidth of the FRB.
        """
        return self._obs_bandwidth

    @obs_bandwidth.setter
    def obs_bandwidth(self, value):
        self._obs_bandwidth = self._set_value_units(value, u.MHz,
                                                    non_negative=True)

    @property
    def raj(self):
        """
        :obj:`astropy.coordinates.Longitude` or None:
            The right accension in J2000 coordinates of the best estimate of
            the FRB position.
        """
        return self._raj

    @raj.setter
    def raj(self, value):
        if value is None:
            self._raj = None
        else:
            self._raj = coord.angles.Longitude(value, u.hourangle)

    @property
    def decj(self):
        """
        :obj:`astropy.coordinates.Latitude` or None:
            The declination in J2000 coordinates of the best estimate of the
            FRB position.
        """
        return self._decj

    @decj.setter
    def decj(self, value):
        if value is None:
            self._decj = None
        else:
            self._decj = coord.angles.Latitude(value, u.deg)

    @property
    def gl(self):
        """
        :obj:`astropy.coordinates.Longitude` or None:
            The longitude in galactic coordinates of the best estimate of the
            FRB position.
        """
        return self._gl

    @gl.setter
    def gl(self, value):
        if value is None:
            self._gl = None
        else:
            self._gl = coord.angles.Longitude(value, u.deg)

    @property
    def gb(self):
        """
        :obj:`astropy.coordinates.Latitude` or None:
            The latitude in galactic coordinates of the best estimate of the
            FRB position.
        """
        return self._gb

    @gb.setter
    def gb(self, value):
        if value is None:
            self._gb = None
        else:
            self._gb = coord.angles.Latitude(value, u.deg)

    @property
    def skycoords(self):
        """
        :obj:`astropy.coordinates.SkyCoord` or None:
            The skycoords of the FRB. This is calculated from either
            (:attr:`raj`, :attr:`decj`) or (:attr:`gl`, :attr:`gb`) using
            :meth:`calc_skycoords`.
        """
        return self._skycoords

    @skycoords.setter
    def skycoords(self, value):
        if value is None:
            self._skycoords = None
        else:
            self._skycoords = SkyCoord(value)

    @property
    def dm_igm(self):
        """
        :obj:`astropy.units.Quantity` or None:
            The estimated disperison measure from the IGM. This can be
            calculated for a FRB for which the redshift of its host galaxy is
            known. This value is determined using :meth:`calc_dm_igm`.
        """
        return self._dm_igm

    @dm_igm.setter
    def dm_igm(self, value):
        self._dm_igm = self._set_value_units(value, u.pc * u.cm**-3,
                                             non_negative=True)

    @property
    def utc(self):
        """
        :obj:`astropy.time.Time` or None:
            The UTC time of the burst.
        """
        return self._utc

    @utc.setter
    def utc(self, value):
        if value is None:
            self._utc = None
        else:
            self._utc = Time(value, format='isot', scale='utc')
