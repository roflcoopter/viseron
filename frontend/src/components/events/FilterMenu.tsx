import {
  ChevronLeft,
  FunnelSort,
} from "@carbon/icons-react";
import Checkbox from "@mui/material/Checkbox";
import IconButton from "@mui/material/IconButton";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import { NestedMenuItem } from "mui-nested-menu";
import React, { MouseEvent, useState } from "react";

import {
  FilterKeysFromFilters,
  getIconFromType,
  useFilterStore,
} from "components/events/utils";
import * as types from "lib/types";

interface MenuProps {
  anchorOrigin: {
    vertical: "bottom" | "top";
    horizontal: "left" | "right";
  };
  transformOrigin: {
    vertical: "bottom" | "top";
    horizontal: "left" | "right";
  };
}

const menuProps: MenuProps = {
  anchorOrigin: {
    vertical: "top",
    horizontal: "left",
  },
  transformOrigin: {
    vertical: "top",
    horizontal: "right",
  },
};

export function FilterMenu() {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);
  const { filters, toggleFilter } = useFilterStore();

  const handleClick = (event: MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleCheckboxClick =
    (filterKey: FilterKeysFromFilters) => (event: MouseEvent<HTMLElement>) => {
      event.stopPropagation();
      event.preventDefault();
      toggleFilter(filterKey);
    };

  return (
    <>
      <IconButton
        onClick={handleClick}
        sx={(theme) => ({
          borderRadius: 0,
          color: theme.palette.primary.main,
        })}
      >
        <FunnelSort size={20}/>
      </IconButton>
      <Menu
        id="filter-menu"
        anchorEl={anchorEl}
        keepMounted
        open={Boolean(anchorEl)}
        onClose={handleClose}
      >
        <NestedMenuItem
          leftIcon={<ChevronLeft size={20}/>}
          rightIcon={<div />}
          label="Events"
          parentMenuOpen={open}
          MenuProps={menuProps}
        >
          {Object.keys(filters.eventTypes).map((filterKey) => {
            const key = filterKey as types.CameraEvent["type"];
            const Icon = getIconFromType(key);
            return (
              <MenuItem
                key={filters.eventTypes[key].label}
                onClick={handleCheckboxClick(key)}
              >
                <Checkbox
                  checked={filters.eventTypes[key].checked}
                  onClick={handleCheckboxClick(key)}
                />
                <ListItemIcon>
                  <Icon />
                </ListItemIcon>
                <ListItemText primary={filters.eventTypes[key].label} />
              </MenuItem>
            );
          })}
        </NestedMenuItem>
        <MenuItem
          key="groupCameras"
          onClick={handleCheckboxClick("groupCameras")}
        >
          <Checkbox
            checked={filters.groupCameras.checked}
            onClick={handleCheckboxClick("groupCameras")}
          />
          <ListItemText primary={filters.groupCameras.label} />
        </MenuItem>
        <MenuItem
          key="lookbackAdjust"
          onClick={handleCheckboxClick("lookbackAdjust")}
        >
          <Checkbox
            checked={filters.lookbackAdjust.checked}
            onClick={handleCheckboxClick("lookbackAdjust")}
          />
          <ListItemText primary={filters.lookbackAdjust.label} />
        </MenuItem>
      </Menu>
    </>
  );
}
