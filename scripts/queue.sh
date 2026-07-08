#!/usr/bin/env bash
# Next TS solvers to port: smallest unported files without an #incorrect tag.
# Size = compressed bytes of the source with comments and blank lines stripped,
# so boilerplate and repetitive code rank as simple.
# Usage: queue.sh [-n COUNT]
set -eu

count=1
while getopts n: opt; do
  case $opt in
    n) count=$OPTARG ;;
    *) exit 2 ;;
  esac
done

perl -MCompress::Zlib -e '
  my @ranked;
  for my $path (glob "../arc-synth-bun/programs/solvers/*.ts") {
    my ($id) = $path =~ m{([^/]+)\.ts$};
    next if -f "programs/solvers/$id.dl";
    open(my $fh, "<", $path) or next;
    my $s = do { local $/; <$fh> };
    next if join("\n", (split /\n/, $s)[0..9]) =~ /#incorrect/;
    $s =~ s{/\*.*?\*/}{}gs;
    $s =~ s{^[ \t]*//[^\n]*$}{}gm;
    $s =~ s{^[ \t]*\n}{}gm;
    push @ranked, [length(compress($s)), $id];
  }
  my @sorted = sort { $a->[0] <=> $b->[0] } @ranked;
  printf "%5d  %s\n", @$_ for @sorted[0 .. ($ARGV[0] < @sorted ? $ARGV[0] : @sorted) - 1];
' "$count"
