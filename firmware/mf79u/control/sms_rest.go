package main

import (
	"errors"
	"net/http"
	"strings"
)

// Header authentication is scoped to SMS REST only. Credentials are validated
// against the modem's challenge endpoint for every request, never persisted.
func (a *App) smsHeaderSession(w http.ResponseWriter, r *http.Request) *Session {
	username, password, ok := r.BasicAuth()
	if !ok || username != "admin" || len(password) < 1 || len(password) > 256 {
		failure(w, 401, errors.New("Use Authorization: Basic with username admin and the modem administrator password"))
		return nil
	}
	a.mu.Lock()
	if a.vendorClient == nil {
		a.vendorClient = vendor(a.base)
	}
	v := a.vendorClient
	a.mu.Unlock()
	key, e := v.loginWithKey(password)
	password = ""
	if e != nil {
		failure(w, 401, errors.New("Administrator authentication failed"))
		return nil
	}
	return &Session{v: v, vendorKey: key}
}

// Cookie authentication uses same-origin CSRF checks; explicit Authorization
// authentication does not require cookies, Origin or CSRF headers.
// Reuse the B03 engine for Unicode, pagination, storage and automatic re-login.
func (a *App) smsREST(w http.ResponseWriter, r *http.Request, s *Session) {
	const collection = "/api/v1/sms/messages"
	id := strings.TrimPrefix(r.URL.Path, collection)
	if id != "" {
		id = strings.TrimPrefix(id, "/")
		if !validSMSID(id) {
			failure(w, 400, errors.New("Invalid SMS ID"))
			return
		}
		if r.Method != "DELETE" {
			w.Header().Set("Allow", "DELETE")
			w.WriteHeader(405)
			return
		}
		if e := a.smsAction(s.v, "delete", []string{id}, "", "", s.vendorKey); e != nil {
			a.vendorFailure(w, r, e)
			return
		}
		respond(w, 200, map[string]bool{"ok": true})
		return
	}
	switch r.Method {
	case "GET":
		storage := r.URL.Query().Get("storage")
		if storage == "" {
			storage = "modem"
		}
		if storage != "modem" && storage != "sim" {
			failure(w, 400, errors.New("SMS storage must be modem or sim"))
			return
		}
		value, e := a.smsList(s.v, storage, s.vendorKey)
		if e != nil {
			a.vendorFailure(w, r, e)
			return
		}
		respond(w, 200, normalizeSMSREST(value))
	case "POST":
		var req struct {
			Number string `json:"number"`
			Text   string `json:"text"`
		}
		if e := decode(w, r, &req); e != nil {
			failure(w, 400, e)
			return
		}
		if !numberRE.MatchString(req.Number) || len([]rune(req.Text)) < 1 || len([]rune(req.Text)) > 670 {
			failure(w, 400, errors.New("Invalid phone number or SMS text (1–670 characters)"))
			return
		}
		if e := a.smsAction(s.v, "send", nil, req.Number, req.Text, s.vendorKey); e != nil {
			a.vendorFailure(w, r, e)
			return
		}
		respond(w, 200, map[string]bool{"ok": true})
	case "DELETE":
		var req struct {
			IDs []string `json:"ids"`
		}
		if e := decode(w, r, &req); e != nil {
			failure(w, 400, e)
			return
		}
		if len(req.IDs) < 1 || len(req.IDs) > 100 {
			failure(w, 400, errors.New("Select 1–100 messages"))
			return
		}
		for _, id := range req.IDs {
			if !validSMSID(id) {
				failure(w, 400, errors.New("Invalid SMS ID"))
				return
			}
		}
		if e := a.smsAction(s.v, "delete", req.IDs, "", "", s.vendorKey); e != nil {
			a.vendorFailure(w, r, e)
			return
		}
		respond(w, 200, map[string]bool{"ok": true})
	default:
		w.Header().Set("Allow", "GET, POST, DELETE")
		w.WriteHeader(405)
	}
}
