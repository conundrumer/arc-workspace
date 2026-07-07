#!/usr/bin/env bash
# Next TS solver to port: smallest unported file without an #incorrect tag.
# Size = compressed bytes of the source with comments and blank lines stripped,
# so boilerplate and repetitive code rank as simple.
set -eu

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
  my ($best) = sort { $a->[0] <=> $b->[0] } @ranked;
  printf "%5d  %s\n", @$best if $best;
'
