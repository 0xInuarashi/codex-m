# Interactive sessions share the service used by mobile. Keep maintenance and
# non-interactive commands local, and honor an explicit --remote or --no-daemon.
unalias codex-m 2>/dev/null || true
codex-m() {
    local codex_m_use_remote=1 codex_m_seen_command=0 codex_m_skip_value=0
    local codex_m_arg
    local -a codex_m_defaults=(--yolo)

    for codex_m_arg in "$@"; do
        if (( codex_m_skip_value )); then
            codex_m_skip_value=0
            continue
        fi
        case "$codex_m_arg" in
            --) break ;;
            --remote)
                codex_m_use_remote=0
                codex_m_skip_value=1
                ;;
            --remote=*|--no-daemon) codex_m_use_remote=0 ;;
            --yolo|--dangerously-bypass-approvals-and-sandbox)
                codex_m_defaults=()
                ;;
            -c|--config|-m|--model|-i|--image|-p|--profile|-s|--sandbox|\
            -C|--cd|-a|--ask-for-approval|--enable|--disable|--local-provider|\
            --remote-auth-token-env|--add-dir)
                codex_m_skip_value=1
                ;;
            -*) ;;
            *)
                if (( ! codex_m_seen_command )); then
                    case "$codex_m_arg" in
                        exec|e|review|login|logout|mcp|plugin|app-server|\
                        remote-control|completion|update|doctor|sandbox|debug|\
                        apply|a|queue|archive|delete|migrate-rollouts|migrate-nfs-db|\
                        unarchive|cloud|cloud-tasks|exec-server|features|help|app|\
                        tcp-tunnel|git-credential|execpolicy|responses-api-proxy|stdio-to-uds)
                            codex_m_use_remote=0
                            ;;
                    esac
                    codex_m_seen_command=1
                fi
                ;;
        esac
    done

    if (( codex_m_use_remote )); then
        codex_m_defaults+=(--remote unix://)
    fi
    command codex-m "${codex_m_defaults[@]}" "$@"
}

alias codex='codex-m --yolo'
alias codex-o='command codex --yolo'
