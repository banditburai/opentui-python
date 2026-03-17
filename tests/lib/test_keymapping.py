"""Port of upstream keymapping.test.ts.

Upstream: packages/core/src/lib/keymapping.test.ts
Tests ported: 29/29 (0 skipped)
"""

from opentui.keymapping import (
    DEFAULT_KEY_ALIASES,
    KeyBinding,
    build_key_bindings_map,
    get_key_binding_key,
    key_binding_to_string,
    merge_key_aliases,
    merge_key_bindings,
)


class TestGetKeyBindingKey:
    """Maps to describe("getKeyBindingKey")."""

    def test_should_generate_key_with_meta_modifier(self):
        """Maps to it("should generate key with meta modifier")."""
        binding = KeyBinding(name="x", action="test", meta=True)
        key = get_key_binding_key(binding)
        assert "x" in key
        # meta flag should be 1
        parts = key.split(":")
        assert parts[3] == "1"  # meta position

    def test_should_generate_different_keys_for_different_modifiers(self):
        """Maps to it("should generate different keys for different modifiers")."""
        b1 = KeyBinding(name="x", action="test", ctrl=True)
        b2 = KeyBinding(name="x", action="test", shift=True)
        assert get_key_binding_key(b1) != get_key_binding_key(b2)

    def test_should_handle_combined_modifiers(self):
        """Maps to it("should handle combined modifiers")."""
        binding = KeyBinding(name="x", action="test", ctrl=True, shift=True)
        key = get_key_binding_key(binding)
        parts = key.split(":")
        assert parts[1] == "1"  # ctrl
        assert parts[2] == "1"  # shift

    def test_should_generate_key_with_super_modifier(self):
        """Maps to it("should generate key with super modifier")."""
        binding = KeyBinding(name="s", action="save", super_key=True)
        key = get_key_binding_key(binding)
        parts = key.split(":")
        assert parts[4] == "1"  # super position


class TestMergeKeyBindings:
    """Maps to describe("mergeKeyBindings")."""

    def test_should_merge_defaults_and_custom_bindings(self):
        """Maps to it("should merge defaults and custom bindings")."""
        defaults = [KeyBinding(name="a", action="alpha")]
        custom = [KeyBinding(name="b", action="beta")]
        merged = merge_key_bindings(defaults, custom)
        assert len(merged) == 2
        actions = {b.action for b in merged}
        assert "alpha" in actions
        assert "beta" in actions

    def test_should_allow_custom_to_override_defaults(self):
        """Maps to it("should allow custom to override defaults")."""
        defaults = [KeyBinding(name="a", action="old")]
        custom = [KeyBinding(name="a", action="new")]
        merged = merge_key_bindings(defaults, custom)
        assert len(merged) == 1
        assert merged[0].action == "new"

    def test_should_override_when_meta_matches(self):
        """Maps to it("should override when meta matches")."""
        defaults = [KeyBinding(name="x", action="old", meta=True)]
        custom = [KeyBinding(name="x", action="new", meta=True)]
        merged = merge_key_bindings(defaults, custom)
        assert len(merged) == 1
        assert merged[0].action == "new"


class TestBuildKeyBindingsMap:
    """Maps to describe("buildKeyBindingsMap")."""

    def test_should_build_map_from_bindings(self):
        """Maps to it("should build map from bindings")."""
        bindings = [KeyBinding(name="a", action="alpha"), KeyBinding(name="b", action="beta")]
        result = build_key_bindings_map(bindings)
        assert len(result) == 2

    def test_should_handle_meta_modifier_correctly(self):
        """Maps to it("should handle meta modifier correctly")."""
        bindings = [KeyBinding(name="x", action="test", meta=True)]
        result = build_key_bindings_map(bindings)
        key = get_key_binding_key(bindings[0])
        assert result[key] == "test"

    def test_should_handle_aliases_and_normalize_key_names(self):
        """Maps to it("should handle aliases and normalize key names")."""
        bindings = [KeyBinding(name="enter", action="submit")]
        aliases = {"enter": "return"}
        result = build_key_bindings_map(bindings, aliases)
        # Should have both the original and aliased key
        enter_key = get_key_binding_key(KeyBinding(name="enter", action="submit"))
        return_key = get_key_binding_key(KeyBinding(name="return", action="submit"))
        assert result[enter_key] == "submit"
        assert result[return_key] == "submit"

    def test_should_create_aliased_mappings_for_aliased_key_names(self):
        """Maps to it("should create aliased mappings for aliased key names")."""
        bindings = [KeyBinding(name="esc", action="cancel")]
        aliases = {"esc": "escape"}
        result = build_key_bindings_map(bindings, aliases)
        escape_key = get_key_binding_key(KeyBinding(name="escape", action="cancel"))
        assert result[escape_key] == "cancel"

    def test_should_handle_multiple_aliases(self):
        """Maps to it("should handle multiple aliases")."""
        bindings = [
            KeyBinding(name="enter", action="submit"),
            KeyBinding(name="esc", action="cancel"),
        ]
        aliases = {"enter": "return", "esc": "escape"}
        result = build_key_bindings_map(bindings, aliases)
        assert len(result) == 4  # 2 original + 2 aliased

    def test_should_handle_aliases_with_modifiers(self):
        """Maps to it("should handle aliases with modifiers")."""
        bindings = [KeyBinding(name="enter", action="submit", ctrl=True)]
        aliases = {"enter": "return"}
        result = build_key_bindings_map(bindings, aliases)
        aliased_key = get_key_binding_key(KeyBinding(name="return", action="submit", ctrl=True))
        assert result[aliased_key] == "submit"


class TestMergeKeyAliases:
    """Maps to describe("mergeKeyAliases")."""

    def test_should_merge_default_and_custom_aliases(self):
        """Maps to it("should merge default and custom aliases")."""
        defaults = {"enter": "return"}
        custom = {"bs": "backspace"}
        result = merge_key_aliases(defaults, custom)
        assert result["enter"] == "return"
        assert result["bs"] == "backspace"

    def test_should_allow_custom_aliases_to_override_defaults(self):
        """Maps to it("should allow custom aliases to override defaults")."""
        defaults = {"enter": "return"}
        custom = {"enter": "newline"}
        result = merge_key_aliases(defaults, custom)
        assert result["enter"] == "newline"

    def test_should_preserve_defaults_when_no_custom_aliases_provided(self):
        """Maps to it("should preserve defaults when no custom aliases provided")."""
        defaults = {"enter": "return", "esc": "escape"}
        result = merge_key_aliases(defaults, {})
        assert result == defaults


class TestDefaultKeyAliases:
    """Maps to describe("defaultKeyAliases")."""

    def test_should_have_enter_to_return_alias(self):
        """Maps to it("should have enter -> return alias")."""
        assert DEFAULT_KEY_ALIASES["enter"] == "return"

    def test_should_have_esc_to_escape_alias(self):
        """Maps to it("should have esc -> escape alias")."""
        assert DEFAULT_KEY_ALIASES["esc"] == "escape"


class TestAliasOverrideBehavior:
    """Maps to describe("alias override behavior")."""

    def test_should_override_return_binding_when_custom_provides_enter_with_aliases(self):
        """Maps to it("should override 'return' binding when custom provides 'enter' binding with aliases")."""
        defaults = [KeyBinding(name="return", action="newline")]
        custom = [KeyBinding(name="enter", action="submit")]
        aliases = {"enter": "return"}
        merged = merge_key_bindings(defaults, custom)
        result = build_key_bindings_map(merged, aliases)
        return_key = get_key_binding_key(KeyBinding(name="return", action=""))
        # The aliased enter->return should map to "submit"
        assert result[return_key] == "submit"

    def test_should_also_allow_direct_override_using_canonical_name(self):
        """Maps to it("should also allow direct override using canonical name")."""
        defaults = [KeyBinding(name="return", action="old")]
        custom = [KeyBinding(name="return", action="new")]
        merged = merge_key_bindings(defaults, custom)
        assert len(merged) == 1
        assert merged[0].action == "new"

    def test_should_handle_textarea_scenario_defaults_with_return_custom_with_enter(self):
        """Maps to it("should handle the Textarea scenario: defaults with 'return', custom with 'enter'")."""
        defaults = [KeyBinding(name="return", action="newline")]
        custom = [KeyBinding(name="enter", action="submit")]
        aliases = {"enter": "return"}
        merged = merge_key_bindings(defaults, custom)
        result = build_key_bindings_map(merged, aliases)
        return_key = get_key_binding_key(KeyBinding(name="return", action=""))
        assert result[return_key] == "submit"


class TestKeyBindingToString:
    """Maps to describe("keyBindingToString")."""

    def test_should_convert_simple_key_binding_without_modifiers(self):
        """Maps to it("should convert simple key binding without modifiers")."""
        assert key_binding_to_string(KeyBinding(name="escape", action="cancel")) == "escape"

    def test_should_convert_key_binding_with_ctrl_modifier(self):
        """Maps to it("should convert key binding with ctrl modifier")."""
        assert key_binding_to_string(KeyBinding(name="c", action="copy", ctrl=True)) == "ctrl+c"

    def test_should_convert_key_binding_with_shift_modifier(self):
        """Maps to it("should convert key binding with shift modifier")."""
        assert (
            key_binding_to_string(KeyBinding(name="tab", action="indent", shift=True))
            == "shift+tab"
        )

    def test_should_convert_key_binding_with_multiple_modifiers(self):
        """Maps to it("should convert key binding with multiple modifiers")."""
        result = key_binding_to_string(KeyBinding(name="y", action="test", ctrl=True, shift=True))
        assert result == "ctrl+shift+y"

    def test_should_convert_key_binding_with_all_modifiers(self):
        """Maps to it("should convert key binding with all modifiers")."""
        result = key_binding_to_string(
            KeyBinding(name="z", action="test", ctrl=True, shift=True, meta=True, super_key=True)
        )
        assert result == "ctrl+shift+meta+super+z"

    def test_should_convert_key_binding_with_meta_modifier(self):
        """Maps to it("should convert key binding with meta modifier")."""
        result = key_binding_to_string(KeyBinding(name="x", action="cut", meta=True))
        assert result == "meta+x"

    def test_should_convert_key_binding_with_super_modifier(self):
        """Maps to it("should convert key binding with super modifier")."""
        result = key_binding_to_string(KeyBinding(name="s", action="save", super_key=True))
        assert result == "super+s"

    def test_should_handle_special_keys_correctly(self):
        """Maps to it("should handle special keys correctly")."""
        assert key_binding_to_string(KeyBinding(name="return", action="submit")) == "return"
        assert key_binding_to_string(KeyBinding(name="backspace", action="delete")) == "backspace"
