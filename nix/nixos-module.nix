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

      script =
        let
          tokenLoader = lib.optionalString (cfg.telegram-bot-token-file != null) ''
            export STATUSPAGE_TELEGRAM_BOT_TOKEN="$(cat ${cfg.telegram-bot-token-file})"
          '';
        in
        ''
          ${tokenLoader}
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
