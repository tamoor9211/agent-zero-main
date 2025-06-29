# shell.nix
{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = [
    pkgs.python312
    pkgs.python312Packages.grpcio
    # pkgs.gcc # Keep commented unless specifically needed
  ];
}