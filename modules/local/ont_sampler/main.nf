process ONT_SAMPLER {
    tag "$meta.id"
    label 'process_low'
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        'oras://ghcr.io/jimmyliu1326/ont_sampler:latest':
        'docker.io/jimmyliu1326/ont_sampler:latest' }"

    input:
    tuple val(meta), path(tsv)

    output:
    tuple val(meta), path("*.csv")                               , emit: csv
    path "versions.yml"                                          , emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    promethion-sampler.py \
        -d ${directory} \
        -s ${sheet} \
        ${args}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        Python: \$(python3 --version | sed 's/Python //g')
    END_VERSIONS
    """

    stub:
    def args = task.ext.args ?: ''
    def prefix = task.ext.prefix ?: "${meta.id}"
    // TODO nf-core: A stub section should mimic the execution of the original module as best as possible
    //               Have a look at the following examples:
    //               Simple example: https://github.com/nf-core/modules/blob/818474a292b4860ae8ff88e149fbcda68814114d/modules/nf-core/bcftools/annotate/main.nf#L47-L63
    //               Complex example: https://github.com/nf-core/modules/blob/818474a292b4860ae8ff88e149fbcda68814114d/modules/nf-core/bedtools/split/main.nf#L38-L54
    """
    touch ${prefix}.tsv
    mkdir -p logs
    touch logs/samnsorter.log

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        samnsorter: \$(SamnSorter.R --version |& sed '1!d ; s/samnsorter v//')
    END_VERSIONS
    """
}