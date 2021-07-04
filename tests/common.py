"""Helper functions for testing."""
import numpy as np


def assert_config_instance_config_dict(config_instance, config_dict, ignore_keys=[]):
    """Assert that all keys in a dict is represented as properties on a class."""
    # print("------------------------------")
    for key, value in config_dict.items():
        if key in ignore_keys:
            continue
        if isinstance(value, dict):
            if isinstance(config_instance, dict):
                assert_config_instance_config_dict(
                    config_instance[key], value, ignore_keys
                )
            else:
                assert_config_instance_config_dict(
                    getattr(config_instance, key, config_instance), value, ignore_keys
                )
        else:
            if isinstance(value, list):
                if isinstance(config_instance, dict):
                    for config_instance_list, config_dict_list in zip(
                        config_instance[key], value
                    ):
                        assert_config_instance_config_dict(
                            config_instance_list, config_dict_list, ignore_keys
                        )
                elif isinstance(getattr(config_instance, key, config_instance), list):
                    try:
                        np.testing.assert_array_equal(
                            value, getattr(config_instance, key)
                        )
                        # print(f"1: {key} {value}")
                        # print(f"1: {key} {getattr(config_instance, key)}")
                        continue
                    except AssertionError:
                        pass
                    for config_instance_element, value_element in zip(
                        getattr(config_instance, key, config_instance), value
                    ):
                        if isinstance(value_element, dict):
                            assert_config_instance_config_dict(
                                config_instance_element, value_element, ignore_keys
                            )
                        else:
                            # print(f"2: {key} {value_element}")
                            # print(f"2: {key} {getattr(config_instance_element, key)}")
                            assert value_element == getattr(
                                config_instance_element, key
                            )
                else:
                    np.testing.assert_array_equal(value, getattr(config_instance, key))
            elif isinstance(config_instance, dict):
                # print(f"3: {key} {value}")
                # print(f"3: {key} {config_instance[key]}")
                assert value == config_instance[key]
            else:
                # print(f"4: {key} {value}")
                # print(f"4: {key} {getattr(config_instance, key)}")
                assert value == getattr(config_instance, key)
