import ChevronLeftIcon from "@mui/icons-material/ChevronLeft";
import FilterListIcon from "@mui/icons-material/FilterList";
import {
  Checkbox,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
} from "@mui/material";
import IconButton from "@mui/material/IconButton";
import { NestedMenuItem } from "mui-nested-menu";
import React, { MouseEvent, useState } from "react";

import { getIconFromType, useFilterStore } from "components/events/utils";
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

export const FilterMenu: React.FC = () => {
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
    (filterKey: types.CameraEvent["type"]) =>
    (event: MouseEvent<HTMLElement>) => {
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
        <FilterListIcon />
      </IconButton>
      <Menu
        id="filter-menu"
        anchorEl={anchorEl}
        keepMounted
        open={Boolean(anchorEl)}
        onClose={handleClose}
      >
        <NestedMenuItem
          leftIcon={<ChevronLeftIcon />}
          rightIcon={<div />}
          label="Events"
          parentMenuOpen={open}
          MenuProps={menuProps}
        >
          {Object.keys(filters).map((filterKey) => {
            const key = filterKey as types.CameraEvent["type"];
            const Icon = getIconFromType(key);
            return (
              <MenuItem
                key={filters[key].label}
                onClick={handleCheckboxClick(key)}
              >
                <Checkbox
                  checked={filters[key].checked}
                  onClick={handleCheckboxClick(key)}
                />
                <ListItemIcon>
                  <Icon />
                </ListItemIcon>
                <ListItemText primary={filters[key].label} />
              </MenuItem>
            );
          })}
        </NestedMenuItem>
      </Menu>
    </>
  );
};
