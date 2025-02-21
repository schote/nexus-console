"""Implementation of a proxy for acquisition parameters."""
import console
from console.interfaces.dimensions import Dimensions
from console.interfaces.enums import DDCMethod


class AcquisitionParameterProxy:
    """Acquisition parameter proxy."""

    def get_larmor_frequency(self) -> float:
        """Get global Lamor frequency.

        Returns
        -------
            Larmor frequency in Hz
        """
        return console.parameter.larmor_frequency

    def set_larmor_frequency(self, value: float) -> None:
        """Set global Larmor frequency.

        Parameters
        ----------
        value
            Larmor frequency in Hz
        """
        console.parameter.larmor_frequency = value

    def get_b1_scaling(self) -> float:
        """Get global $B_1$ scaling factor.

        Returns
        -------
            $B_1$ scaling value / arbitrary unit
        """
        return console.parameter.b1_scaling

    def set_b1_scaling(self, value: float) -> None:
        """Set global $B_1$ scaling value.

        Parameters
        ----------
        value
            $B_1$ scaling value / arbitrary unit
        """
        console.parameter.b1_scaling = value

    def get_gradient_offset(self) -> Dimensions:
        """Get global gradient offsets used for active shimming.

        Returns
        -------
            Gradient offsets per dimension x, y and z
        """
        return console.parameter.gradient_offset

    def set_gradient_offset(self, value: Dimensions) -> None:
        """Set global gradient offsets for active shimming.

        Parameters
        ----------
        value
            Values to be set for x, y and z
        """
        console.parameter.gradient_offset = value

    def get_fov_scaling(self) -> Dimensions:
        """Get global FoV scaling, arbitrary units.

        Returns
        -------
            FoV values for x, y and z
        """
        return console.parameter.fov_scaling

    def set_fov_scaling(self, value: Dimensions) -> None:
        """Set global FoV scaling, arbitrary units.

        Parameters
        ----------
        value
            FoV values for x, y and z.
        """
        console.parameter.fov_scaling = value

    def get_decimation(self) -> int:
        """Get global decimation factor.

        Returns
        -------
            Decimation value
        """
        return console.parameter.decimation

    def set_decimation(self, value: int) -> None:
        """Set global decimation factor.

        Parameters
        ----------
        value
            Decimation value
        """
        console.parameter.decimation = value

    def get_ddc_method(self) -> DDCMethod:
        """Get global DDC method for decimation.

        Returns
        -------
            DDC method
        """
        return console.parameter.ddc_method

    def set_ddc_method(self, value: DDCMethod) -> None:
        """Set global DDC method.

        Parameters
        ----------
        value
            DDC method
        """
        console.parameter.ddc_method = value

    def get_num_averages(self) -> int:
        """Get global number of averages.

        Returns
        -------
            Number of averages
        """
        return console.parameter.num_averages

    def set_num_averages(self, value: int) -> None:
        """Set global number of averages.

        Parameters
        ----------
        value
            Number of averages.
        """
        console.parameter.num_averages = value

    def get_averaging_delay(self) -> float:
        """Get global delay between averages.

        Returns
        -------
            Delay value in s
        """
        return console.parameter.averaging_delay

    def set_averaging_delay(self, value: float) -> None:
        """Set global delay between averages.

        Parameters
        ----------
        value
            Delay value in s
        """
        console.parameter.averaging_delay = value
