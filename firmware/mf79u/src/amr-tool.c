/* Local PCM/AMR-NB conversion only. No radio, device nodes, network or ioctls. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <interf_enc.h>
#include <interf_dec.h>

static const int payload_sizes[16] = {12,13,15,17,19,20,26,31,5,-1,-1,-1,-1,-1,-1,0};
static double seconds(void) {
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now)) return 0;
    return (double)now.tv_sec + (double)now.tv_nsec / 1000000000.0;
}
int main(int argc, char **argv) {
    if (argc != 4 || (strcmp(argv[1], "encode") && strcmp(argv[1], "decode"))) {
        fprintf(stderr, "Usage: %s encode input.s16le output.amr | decode input.amr output.s16le\n"
            "PCM is 8000 Hz mono signed 16-bit LE; encoding is AMR-NB MR122, no DTX.\n", argv[0]);
        return 1;
    }
    if (!strcmp(argv[2], argv[3])) { fprintf(stderr, "Input and output must differ\n"); return 1; }
    FILE *input = fopen(argv[2], "rb");
    if (!input) { perror("input"); return 1; }
    FILE *output = fopen(argv[3], "wb");
    if (!output) { perror("output"); fclose(input); return 1; }
    int encode = !strcmp(argv[1], "encode"), failed = 0;
    void *state = encode ? Encoder_Interface_init(0) : Decoder_Interface_init();
    if (!state) { fprintf(stderr, "Codec initialization failed\n"); fclose(input); fclose(output); return 1; }
    if (encode) {
        if (fwrite("#!AMR\n", 1, 6, output) != 6) failed = 1;
    } else {
        char header[6];
        if (fread(header, 1, 6, input) != 6 || memcmp(header, "#!AMR\n", 6)) {
            fprintf(stderr, "Invalid AMR-NB file header\n"); failed = 1;
        }
    }
    unsigned long frames = 0;
    double start = seconds();
    while (!failed) {
        unsigned char pcm_bytes[320], encoded[64];
        short samples[160];
        if (encode) {
            size_t count = fread(pcm_bytes, 1, 320, input);
            if (!count) break;
            if (count != 320) { fprintf(stderr, "Partial PCM frame\n"); failed = 1; break; }
            for (int i = 0; i < 160; ++i)
                samples[i] = (int16_t)((unsigned)pcm_bytes[2*i] | ((unsigned)pcm_bytes[2*i+1] << 8));
            int count_out = Encoder_Interface_Encode(state, MR122, samples, encoded, 0);
            if (count_out != 32 || fwrite(encoded, 1, count_out, output) != (size_t)count_out) failed = 1;
        } else {
            if (fread(encoded, 1, 1, input) != 1) break;
            int frame_type = (encoded[0] >> 3) & 15;
            int size = payload_sizes[frame_type];
            if ((encoded[0] & 0x83) || size < 0 || fread(encoded+1, 1, size, input) != (size_t)size) {
                fprintf(stderr, "Invalid or truncated AMR frame\n"); failed = 1; break;
            }
            Decoder_Interface_Decode(state, encoded, samples, !(encoded[0] & 4));
            for (int i = 0; i < 160; ++i) {
                pcm_bytes[2*i] = (uint16_t)samples[i] & 255;
                pcm_bytes[2*i+1] = (uint16_t)samples[i] >> 8;
            }
            if (fwrite(pcm_bytes, 1, 320, output) != 320) failed = 1;
        }
        if (!failed) ++frames;
    }
    double elapsed = seconds() - start;
    if (ferror(input)) failed = 1;
    if (encode) Encoder_Interface_exit(state); else Decoder_Interface_exit(state);
    if (fclose(output)) failed = 1;
    fclose(input);
    fprintf(stderr, "{\"operation\":\"%s\",\"frames\":%lu,\"audio_seconds\":%.3f,"
        "\"elapsed_seconds\":%.6f,\"success\":%s}\n", argv[1], frames, frames*0.02, elapsed,
        failed ? "false" : "true");
    return failed ? 2 : 0;
}
