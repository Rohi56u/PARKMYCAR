"""
Unit tests for SyntheticPlateGenerator.
"""
import numpy as np
import pytest

from anpr_service.synthetic import (
    PlateColorTheme,
    PlateLayout,
    DistortionType,
    DistortionConfig,
    SyntheticPlateResult,
    SyntheticPlateGenerator,
)


def test_synthetic_plate_generation_single_row():
    """Verify single-row plate generation across color palettes."""
    gen = SyntheticPlateGenerator()

    themes = [
        PlateColorTheme.PRIVATE_WHITE,
        PlateColorTheme.COMMERCIAL_YELLOW,
        PlateColorTheme.EV_GREEN,
        PlateColorTheme.RENTAL_BLACK,
        PlateColorTheme.BHARAT_SERIES,
    ]

    for theme in themes:
        res = gen.generate(
            "DL01AB1234",
            theme=theme,
            layout=PlateLayout.SINGLE_ROW,
            distortion_cfg=None,
        )
        assert isinstance(res, SyntheticPlateResult)
        assert res.image.shape == (105, 440, 3)
        assert res.plate_number == "DL01AB1234"
        assert res.theme == theme
        assert res.layout == PlateLayout.SINGLE_ROW
        assert res.state_code == "DL"


def test_synthetic_plate_generation_dual_row():
    """Verify dual-row plate generation."""
    gen = SyntheticPlateGenerator()
    res = gen.generate(
        "KA05M5678",
        theme=PlateColorTheme.COMMERCIAL_YELLOW,
        layout=PlateLayout.DUAL_ROW,
        distortion_cfg=None,
    )
    assert res.image.shape == (180, 300, 3)
    assert res.layout == PlateLayout.DUAL_ROW
    assert res.state_code == "KA"


def test_synthetic_plate_distortions():
    """Verify applying distortions alters the output image and tracks applied distortions."""
    gen = SyntheticPlateGenerator()
    cfg = DistortionConfig(
        enabled=True,
        distortions=[
            DistortionType.GAUSSIAN_BLUR,
            DistortionType.POISSON_NOISE,
            DistortionType.PERSPECTIVE_WARP,
            DistortionType.ILLUMINATION_GRADIENT,
        ],
    )
    res_clean = gen.generate("DL01AB1234", distortion_cfg=None)
    res_distorted = gen.generate("DL01AB1234", distortion_cfg=cfg)

    assert len(res_distorted.distortions_applied) == 4
    # Distorted image pixels should differ from clean image
    diff = np.mean(np.abs(res_clean.image.astype(float) - res_distorted.image.astype(float)))
    assert diff > 1.0


def test_synthetic_all_themes_dual_row():
    """Verify all 8 themes render properly in dual-row format."""
    gen = SyntheticPlateGenerator()
    for theme in PlateColorTheme:
        res = gen.generate("DL01AB1234", theme=theme, layout=PlateLayout.DUAL_ROW)
        assert res.image.shape == (180, 300, 3)
        assert res.theme == theme


def test_synthetic_road_grime_distortion():
    """Verify road grime distortion applies without errors."""
    gen = SyntheticPlateGenerator()
    cfg = DistortionConfig(
        enabled=True,
        distortions=[DistortionType.ROAD_GRIME],
    )
    res = gen.generate("DL01AB1234", distortion_cfg=cfg)
    assert DistortionType.ROAD_GRIME in res.distortions_applied
