{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = [
    pkgs.python310
    pkgs.python310Packages.virtualenv
  ];

  shellHook = ''
    # Create and activate a virtual environment
    python3 -m venv venv
    source venv/bin/activate

    # Install required packages
    pip install -r requirements.txt
  '';
}
