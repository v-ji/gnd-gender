{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  };

  outputs =
    {
      self,
      nixpkgs,
    }:
    let
      forAllSystems =
        function:
        nixpkgs.lib.genAttrs [
          "aarch64-linux"
          "x86_64-linux"
          "aarch64-darwin"
          "x86_64-darwin"
        ] (system: function nixpkgs.legacyPackages.${system});
      pythonDeps =
        ps: with ps; [
          atproto
          lxml
          mastodon-py
          requests
        ];
    in
    {
      nixosModules.default =
        {
          config,
          lib,
          pkgs,
          ...
        }:
        let
          cfg = config.services.gnd-gender;
          otherHours = lib.filter (h: h != cfg.hotHour) (lib.range 0 23);
          runScript = pkgs.writeShellScript "gnd-gender-run" ''
            if [ "$1" = "hot" ]; then
              exec ${lib.getExe cfg.package} --platform ${lib.concatStringsSep " " cfg.platforms}
            else
              exec ${lib.getExe cfg.package} --platform ${lib.concatStringsSep " " cfg.platforms} --filter positive
            fi
          '';
          stopScript = pkgs.writeShellScript "gnd-gender-stop" ''
            if [ "$EXIT_STATUS" = "99" ]; then
              systemctl stop gnd-gender-hot.timer gnd-gender.timer
            fi
          '';
        in
        {
          options.services.gnd-gender = {
            enable = lib.mkEnableOption "GND gender vocabulary bot";
            package = lib.mkOption {
              type = lib.types.package;
              default = self.packages.${pkgs.system}.default;
            };
            platforms = lib.mkOption {
              type = lib.types.nonEmptyListOf lib.types.str;
              default = [
                "bluesky"
                "mastodon"
              ];
            };
            hotHour = lib.mkOption {
              type = lib.types.ints.between 0 23;
              default = 11;
              description = "Hour at which to post any outcome (no --filter).";
            };
            environmentFile = lib.mkOption {
              type = lib.types.nullOr lib.types.path;
              default = null;
              description = "File of KEY=VALUE pairs supplying secrets (ATPROTO_*, MASTODON_*).";
            };
          };

          config = lib.mkIf cfg.enable {
            systemd = {
              services."gnd-gender@" = {
                description = "GND gender vocabulary bot (%i)";
                after = [ "network-online.target" ];
                wants = [ "network-online.target" ];
                serviceConfig = {
                  Type = "oneshot";
                  SuccessExitStatus = [
                    0
                    99
                  ];
                  ExecStart = "${runScript} %i";
                  ExecStopPost = "+${stopScript}";
                }
                // lib.optionalAttrs (cfg.environmentFile != null) {
                  EnvironmentFile = cfg.environmentFile;
                };
              };

              timers.gnd-gender-hot = {
                description = "gnd-gender hot-hour timer";
                wantedBy = [ "timers.target" ];
                timerConfig = {
                  Unit = "gnd-gender@hot.service";
                  OnCalendar = "${toString cfg.hotHour}:05";
                  RandomizedDelaySec = 600;
                  AccuracySec = 1;
                  Persistent = true;
                };
              };

              timers.gnd-gender = {
                description = "gnd-gender regular hourly timer";
                wantedBy = [ "timers.target" ];
                timerConfig = {
                  Unit = "gnd-gender@filtered.service";
                  OnCalendar = "${lib.concatMapStringsSep "," toString otherHours}:05";
                  RandomizedDelaySec = 600;
                  AccuracySec = 1;
                  Persistent = true;
                };
              };
            };
          };
        };

      devShells = forAllSystems (pkgs: {
        default = pkgs.mkShell {
          packages = with pkgs; [
            (python3.withPackages pythonDeps)
          ];
        };
      });

      packages = forAllSystems (
        pkgs:
        let
          pyproject = pkgs.lib.importTOML ./pyproject.toml;
        in
        {
          default =
            with pkgs.python3Packages;
            buildPythonApplication {
              pname = pyproject.project.name;
              version = pyproject.project.version;
              pyproject = true;

              src = ./.;

              build-system = [
                setuptools
                setuptools-scm
              ];

              dependencies = pythonDeps pkgs.python3Packages;

              meta.mainProgram = "gnd-gender";
            };
        }
      );
    };
}
