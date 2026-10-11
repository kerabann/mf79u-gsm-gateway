package main

import (
	"bytes"
	"crypto/sha256"
	"fmt"
	"io/fs"
	"net/http"
	"strings"
	"sync"
	"time"
)

type staticAsset struct {
	raw, compressed []byte
	etag            string
}

var staticOnce sync.Once
var staticFiles map[string]staticAsset

func serveStatic(w http.ResponseWriter, r *http.Request) {
	if r.Method != "GET" && r.Method != "HEAD" {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}
	staticOnce.Do(func() {
		staticFiles = map[string]staticAsset{}
		entries, _ := fs.ReadDir(assets, "web")
		for _, entry := range entries {
			if entry.IsDir() {
				continue
			}
			raw, e := assets.ReadFile("web/" + entry.Name())
			if e != nil {
				continue
			}
			packed, _ := assets.ReadFile("web/compressed/" + entry.Name() + ".gz")
			staticFiles[entry.Name()] = staticAsset{raw: raw, compressed: packed, etag: fmt.Sprintf("%x", sha256.Sum256(raw))}
		}
	})
	name := strings.TrimPrefix(r.URL.Path, "/")
	if name == "" {
		name = "index.html"
	}
	asset, ok := staticFiles[name]
	if !ok {
		http.NotFound(w, r)
		return
	}
	// Revalidate embedded scripts after every firmware update, while retaining
	// browser cache and compressed transfers on slow DERP connections.
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Vary", "Accept-Encoding")
	body, suffix := asset.raw, ""
	if len(asset.compressed) > 0 && acceptsGzip(r.Header.Get("Accept-Encoding")) {
		body, suffix = asset.compressed, "-gzip"
		w.Header().Set("Content-Encoding", "gzip")
	}
	w.Header().Set("ETag", `"`+asset.etag+suffix+`"`)
	http.ServeContent(w, r, name, time.Time{}, bytes.NewReader(body))
}
func acceptsGzip(header string) bool {
	for _, token := range strings.Split(header, ",") {
		parts := strings.Split(token, ";")
		if strings.TrimSpace(parts[0]) != "gzip" {
			continue
		}
		for _, parameter := range parts[1:] {
			parameter = strings.TrimSpace(parameter)
			if strings.HasPrefix(parameter, "q=") {
				var q float64
				if _, e := fmt.Sscanf(parameter, "q=%f", &q); e != nil || q <= 0 {
					return false
				}
			}
		}
		return true
	}
	return false
}
