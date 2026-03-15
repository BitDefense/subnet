package api

import (
	"net/http"

	"github.com/BitDefense/subnet/engines/w3/internal/invariant"
	"github.com/BitDefense/subnet/engines/w3/internal/models"
	"github.com/labstack/echo/v4"
)

type handler struct {
	engine *invariant.Engine
}

func NewHandler(engine *invariant.Engine) *handler {
	return &handler{
		engine: engine,
	}
}

func (h *handler) Register(g *echo.Group) {
	g.POST("/check", h.Check)
}

func (h *handler) Check(c echo.Context) error {
	challenge := models.Challenge{}
	if err := c.Bind(&challenge); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, err.Error())
	}

	result, err := h.engine.ExecuteCheck(c.Request().Context(), challenge)
	if err != nil {
		return echo.NewHTTPError(http.StatusInternalServerError, err.Error())
	}

	return c.JSON(http.StatusOK, result)
}
