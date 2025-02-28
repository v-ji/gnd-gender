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
          requests
        ];
    in
    {
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
            };
        }
      );
    };
}
