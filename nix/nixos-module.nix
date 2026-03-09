{ config, lib, pkgs, ... }:
let
  cfg = config.services.statuspage;
in
{
  options.services.statuspage = {
    enable = lib.mkEnableOption "the statuspage service";

    package = lib.mkPackageOption pkgs "statuspage" { };

    data-path = lib.mkOption {
      type = lib.types.str;
      default = "/var/lib/statuspage";
      description = "Directory where statuspage stores its SQLite database and data files.";
    };

    base-url = lib.mkOption {
      type = lib.types.str;
      description = "Public base URL of the statuspage (e.g. https://status.example.com).";
      example = "https://status.example.com";
    };

    listen-host = lib.mkOption {
      type = lib.types.str;
      default = "127.0.0.1";
      description = "Host on which the backend listens for incoming connections.";
    };

    listen-port = lib.mkOption {
      type = lib.types.int;
      default = 8001;
      description = "Port on which the backend listens for incoming connections.";
    };

    telegram-bot-token-file = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = null;
      description = "Path to a file containing the Telegram bot token. Optional.";
    };

    telegram-chat-id = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = "Telegram chat ID to send notifications to. Optional.";
    };

    smtp-host = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = "SMTP server hostname. Enables email notifications when set.";
    };

    smtp-port = lib.mkOption {
      type = lib.types.int;
      default = 587;
      description = "SMTP server port. Use 465 for SMTP_SSL, 587 for STARTTLS, 25 for plain relay.";
    };

    smtp-user = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = "SMTP username. Optional — omit for unauthenticated relay.";
    };

    smtp-password-file = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = null;
      description = "Path to a file containing the SMTP password. Optional.";
    };

    smtp-from = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = "From address for outgoing mail. Defaults to smtp-user when unset.";
    };

    smtp-to = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = "Recipient address for email notifications. Required to enable email.";
    };

    smtp-use-starttls = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Whether to issue STARTTLS after connecting. Set false for port-465 SSL or plain relay.";
    };

    nginx-vhost-name = lib.mkOption {
      type = lib.types.str;
      description = "Name of the nginx virtual host (typically the domain name).";
      example = "status.example.com";
    };
  };

  config = lib.mkIf cfg.enable {
    systemd.services.statuspage = {
      description = "Statuspage service";
      wantedBy = [ "multi-user.target" ];
      wants = [ "network-online.target" ];
      after = [ "network-online.target" ];

      path = with pkgs; [ bash coreutils curl openssh nix python3 "/run/current-system/sw" ];
      script =
        let
          tokenLoader = lib.optionalString (cfg.telegram-bot-token-file != null) ''
            export STATUSPAGE_TELEGRAM_BOT_TOKEN="$(cat ${cfg.telegram-bot-token-file})"
          '';
          passwordLoader = lib.optionalString (cfg.smtp-password-file != null) ''
            export STATUSPAGE_SMTP_PASSWORD="$(cat ${cfg.smtp-password-file})"
          '';
        in
        ''
          ${tokenLoader}
          ${passwordLoader}
          exec ${cfg.package}/bin/statuspage
        '';

      serviceConfig = {
        Restart = "always";
        StateDirectory = "statuspage";
        WorkingDirectory = cfg.data-path;
      };

      environment = {
        UVICORN_HOST = cfg.listen-host;
        UVICORN_PORT = builtins.toString cfg.listen-port;
        STATUSPAGE_DATA_PATH = cfg.data-path;
        STATUSPAGE_BASE_URL = cfg.base-url;
      } // lib.optionalAttrs (cfg.telegram-chat-id != null) {
        STATUSPAGE_TELEGRAM_CHAT_ID = cfg.telegram-chat-id;
      } // lib.optionalAttrs (cfg.smtp-host != null) {
        STATUSPAGE_SMTP_HOST = cfg.smtp-host;
        STATUSPAGE_SMTP_PORT = builtins.toString cfg.smtp-port;
        STATUSPAGE_SMTP_USE_STARTTLS = if cfg.smtp-use-starttls then "true" else "false";
      } // lib.optionalAttrs (cfg.smtp-user != null) {
        STATUSPAGE_SMTP_USER = cfg.smtp-user;
      } // lib.optionalAttrs (cfg.smtp-from != null) {
        STATUSPAGE_SMTP_FROM = cfg.smtp-from;
      } // lib.optionalAttrs (cfg.smtp-to != null) {
        STATUSPAGE_SMTP_TO = cfg.smtp-to;
      };

    };

    services.nginx = {
      enable = true;
      virtualHosts.${cfg.nginx-vhost-name} = {
        forceSSL = true;
        enableACME = true;
        locations."/" = {
          proxyPass = "http://${cfg.listen-host}:${builtins.toString cfg.listen-port}";
          recommendedProxySettings = true;
          extraConfig = ''
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_buffer_size          128k;
            proxy_buffers            4 256k;
            proxy_busy_buffers_size    256k;
          '';
        };
      };
    };
  };
}
