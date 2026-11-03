"""Stand-in for the sample build's build_tables.py in the kit: point_tables._writer() imports `sampler_writer` from `build_tables`. In the kit the writer is the module `writer`."""


def sampler_writer():
    import writer
    return writer
