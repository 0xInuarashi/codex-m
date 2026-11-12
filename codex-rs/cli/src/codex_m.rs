//! Fork defaults are loaded natively, without a runtime launcher dependency.
use anyhow::Context;
use std::path::PathBuf;

pub(crate) fn prepend_defaults(overrides: &mut Vec<String>) -> anyhow::Result<()> {
    let home = std::env::var_os("HOME").or_else(|| std::env::var_os("USERPROFILE"));
    let Some(home) = home else { return Ok(()) };
    let path = PathBuf::from(home).join(".config/codex-m/config.toml");
    let source = match std::fs::read_to_string(&path) {
        Ok(source) => source,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            include_str!("../../../scripts/codex-m.defaults.toml").to_owned()
        }
        Err(error) => return Err(error).with_context(|| format!("reading {}", path.display())),
    };
    let table: toml::Table =
        toml::from_str(&source).with_context(|| format!("parsing {}", path.display()))?;
    let mut defaults = Vec::new();
    flatten(&table, "", &mut defaults)?;
    defaults.append(overrides);
    *overrides = defaults;
    Ok(())
}

fn flatten(table: &toml::Table, prefix: &str, overrides: &mut Vec<String>) -> anyhow::Result<()> {
    for (key, value) in table {
        anyhow::ensure!(
            !key.contains('.'),
            "codex-m default keys cannot contain literal dots: {key}"
        );
        let name = if prefix.is_empty() {
            key.clone()
        } else {
            format!("{prefix}.{key}")
        };
        if let toml::Value::Table(table) = value {
            flatten(table, &name, overrides)?;
        } else {
            overrides.push(format!("{name}={value}"));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn defaults_preserve_toml_values_and_literal_keys() {
        let table = toml::from_str(
            "[model_routing]\nsubagent_service_tier = 'ultrafast'\n[example]\nvalue = ['x', 'y']\n",
        )
        .unwrap();
        let mut overrides = Vec::new();
        flatten(&table, "", &mut overrides).unwrap();
        let parsed: toml::Table = toml::from_str(&overrides.join("\n")).unwrap();
        assert_eq!(parsed, table);
    }
}
