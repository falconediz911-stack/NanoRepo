# ==========================================
# NanoOS zsh
# Your own settings can go at the end of this file.
# ==========================================

# Completion (plus the extra completions from zsh-completions)
fpath=(/usr/share/zsh/site-functions $fpath)
autoload -Uz compinit
compinit -d "${XDG_CACHE_HOME:-$HOME/.cache}/zcompdump"
zstyle ':completion:*' menu select
zstyle ':completion:*' matcher-list 'm:{a-z}={A-Z}'
zstyle ':completion:*' list-colors "${(s.:.)LS_COLORS}"

# History
HISTFILE="$HOME/.zsh_history"
HISTSIZE=10000
SAVEHIST=10000
setopt HIST_IGNORE_DUPS HIST_IGNORE_SPACE SHARE_HISTORY

# Quality of life
setopt AUTO_CD INTERACTIVE_COMMENTS
bindkey -e
bindkey '^[[H' beginning-of-line
bindkey '^[[F' end-of-line
bindkey '^[[3~' delete-char
bindkey '^[[1;5C' forward-word
bindkey '^[[1;5D' backward-word
alias ls='ls --color=auto'
alias ll='ls -lh --color=auto'
alias la='ls -lAh --color=auto'
alias grep='grep --color=auto'

export PATH="$HOME/.local/bin:$PATH"

# Prompt: [user@host dir]$
PROMPT='%F{cyan}[%n@%m %~]%f$ '
RPROMPT=''

# Autosuggestions, then syntax highlighting (must load last)
[[ -f /usr/share/zsh/plugins/zsh-autosuggestions/zsh-autosuggestions.zsh ]] &&
    source /usr/share/zsh/plugins/zsh-autosuggestions/zsh-autosuggestions.zsh
[[ -f /usr/share/zsh/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh ]] &&
    source /usr/share/zsh/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh

# System info when a terminal opens
if [[ -o interactive && -t 1 ]] && command -v fastfetch >/dev/null; then
    fastfetch
fi
