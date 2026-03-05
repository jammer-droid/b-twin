from pathlib import Path

import yaml

from btwin.config import BTwinConfig, load_config


def test_default_promotion_schedule_is_daily_twice() -> None:
    cfg = BTwinConfig()

    assert cfg.promotion.enabled is True
    assert cfg.promotion.schedule == "0 9,21 * * *"


def test_load_config_with_custom_promotion_schedule(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        yaml.dump(
            {
                "promotion": {
                    "enabled": True,
                    "schedule": "0 */6 * * *",
                }
            }
        )
    )

    cfg = load_config(cfg_file)
    assert cfg.promotion.schedule == "0 */6 * * *"
