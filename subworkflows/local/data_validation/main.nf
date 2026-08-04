/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    IMPORT MODULES / SUBWORKFLOWS / FUNCTIONS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/
include { ONT_SAMPLER                } from '../../../modules/local/ont_sampler/main'

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    RUN MAIN WORKFLOW
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

workflow DATA_VALIDATION {
    take:
    sheet // channel [ [id:] , path ]

    main:

        // initialize empty channels
        ch_versions = Channel.empty()

        // initialize data directory channel
        ch_data_dir = Channel.
            fromPath( params.data_directory, checkIfExists: true )

        ONT_SAMPLER(
            sheet,
            ch_data_dir
        )

        ch_versions = ch_versions.mix(ONT_SAMPLER.out.versions)

    emit:
    versions = ch_versions
    samnsero_csv = ONT_SAMPLER.out.csv

}