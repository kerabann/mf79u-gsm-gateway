package main

import (
	"bytes"
	"compress/gzip"
	"io"
	"net/http/httptest"
	"testing"
)

func TestStaticCompressionRevalidation(t *testing.T) {
	req := httptest.NewRequest("GET", "/app.js", nil)
	req.Header.Set("Accept-Encoding", "gzip")
	rec := httptest.NewRecorder()
	serveStatic(rec, req)
	if rec.Code != 200 || rec.Header().Get("Content-Encoding") != "gzip" || rec.Header().Get("Cache-Control") != "no-cache" {
		t.Fatal("Missing compressed/revalidated response")
	}
	gz, e := gzip.NewReader(rec.Body)
	if e != nil {
		t.Fatal(e)
	}
	got, e := io.ReadAll(gz)
	if e != nil {
		t.Fatal(e)
	}
	gz.Close()
	want, _ := assets.ReadFile("web/app.js")
	if !bytes.Equal(got, want) {
		t.Fatal("Asset changed during compression")
	}
	req.Header.Set("If-None-Match", rec.Header().Get("ETag"))
	cached := httptest.NewRecorder()
	serveStatic(cached, req)
	if cached.Code != 304 || cached.Body.Len() != 0 {
		t.Fatal("Revalidation did not return 304")
	}
	req.Header.Set("Accept-Encoding", "gzip;q=0")
	plain := httptest.NewRecorder()
	serveStatic(plain, req)
	if plain.Code != 200 || plain.Header().Get("Content-Encoding") != "" || !bytes.Equal(plain.Body.Bytes(), want) {
		t.Fatal("Plain representation is incorrect")
	}
}
